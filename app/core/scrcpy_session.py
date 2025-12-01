import asyncio
import logging

from starlette.websockets import WebSocket, WebSocketDisconnect

from app.config import settings
from app.core.adb_manager import AdbManager
from app.core.port_allocator import PortAllocator
from app.models.device import SessionState

logger = logging.getLogger(__name__)


class ScrcpySession:
    """Manages the full lifecycle of a scrcpy connection for one Android device.

    One instance per device serial. Handles:
    - ADB port forwarding and scrcpy-server process management
    - Three sequential TCP socket connections (video / audio / control)
    - Streaming H.264 chunks to all connected browser clients
    - Forwarding control commands from the browser to the device
    - Graceful shutdown with configurable grace period
    """

    def __init__(self, serial: str, adb: AdbManager, ports: PortAllocator) -> None:
        self.serial = serial
        self.state = SessionState.IDLE

        self._adb = adb
        self._ports = ports
        self._port: int = 0

        self._adb_process: asyncio.subprocess.Process | None = None
        self._video_reader: asyncio.StreamReader | None = None
        self._video_writer: asyncio.StreamWriter | None = None
        self._control_writer: asyncio.StreamWriter | None = None

        self._clients: set[WebSocket] = set()
        self._stop_event = asyncio.Event()
        self._stream_task: asyncio.Task[None] | None = None
        self._grace_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scrcpy session: push JAR, forward port, launch server, connect sockets."""
        if self.state not in (SessionState.IDLE, SessionState.ERROR):
            return

        self.state = SessionState.STARTING
        logger.info("[%s] Starting session", self.serial)

        try:
            await self._adb.push_server(self.serial)
            self._port = await self._ports.acquire()
            await self._adb.forward_port(self.serial, self._port)
            self._adb_process = await self._adb.start_server(self.serial)
            await self._connect_sockets()
            self._stop_event.clear()
            self._stream_task = asyncio.create_task(
                self._stream_loop(), name=f"stream-{self.serial}"
            )
            self.state = SessionState.STREAMING
            logger.info("[%s] Session streaming on port %d", self.serial, self._port)
        except Exception as exc:
            self.state = SessionState.ERROR
            logger.error("[%s] Failed to start session: %s", self.serial, exc)
            await self._cleanup()
            raise

    async def stop(self) -> None:
        """Stop the session and release all resources."""
        if self.state == SessionState.STOPPING:
            return

        self.state = SessionState.STOPPING
        logger.info("[%s] Stopping session", self.serial)

        self._cancel_grace_timer()
        self._stop_event.set()

        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception):
                pass

        await self._notify_clients_disconnected()
        await self._cleanup()
        self.state = SessionState.IDLE
        logger.info("[%s] Session stopped", self.serial)

    async def add_client(self, ws: WebSocket) -> None:
        self._cancel_grace_timer()
        self._clients.add(ws)
        logger.debug("[%s] Client added (%d total)", self.serial, len(self._clients))

    async def remove_client(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        logger.debug("[%s] Client removed (%d total)", self.serial, len(self._clients))
        if not self._clients:
            self._schedule_grace_stop()

    async def send_control(self, data: bytes) -> None:
        """Forward raw control bytes from the browser to the device."""
        if self._control_writer is None:
            return
        try:
            self._control_writer.write(data)
            await self._control_writer.drain()
        except Exception as exc:
            logger.warning("[%s] Control write failed: %s", self.serial, exc)

    # ------------------------------------------------------------------
    # Internal: socket connection
    # ------------------------------------------------------------------

    async def _connect_sockets(self) -> None:
        """Open three sequential TCP connections to the scrcpy-server.

        Order matters: video → audio → control (scrcpy protocol requirement).
        Partial connections are cleaned up on failure.
        """
        for attempt in range(1, settings.socket_connect_retries + 1):
            opened_writers: list[asyncio.StreamWriter] = []
            try:
                # 1. Video socket
                video_reader, video_writer = await asyncio.open_connection(
                    "127.0.0.1", self._port
                )
                opened_writers.append(video_writer)

                # 2. Audio socket — connect to satisfy the protocol, then discard
                _, audio_writer = await asyncio.open_connection("127.0.0.1", self._port)
                audio_writer.close()
                await audio_writer.wait_closed()

                # 3. Control socket
                _, control_writer = await asyncio.open_connection("127.0.0.1", self._port)

                self._video_reader = video_reader
                self._video_writer = video_writer
                self._control_writer = control_writer
                logger.debug("[%s] Sockets connected (attempt %d)", self.serial, attempt)
                return

            except OSError:
                for writer in opened_writers:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass

                if attempt == settings.socket_connect_retries:
                    raise RuntimeError(
                        f"[{self.serial}] Could not connect to scrcpy-server after "
                        f"{settings.socket_connect_retries} attempts"
                    )
                await asyncio.sleep(settings.socket_connect_delay)

    # ------------------------------------------------------------------
    # Internal: video stream loop
    # ------------------------------------------------------------------

    async def _stream_loop(self) -> None:
        """Read H.264 chunks from the TCP socket and broadcast to all clients.

        Runs until _stop_event is set or the TCP connection closes.
        """
        reader = self._video_reader
        if reader is None:
            return

        logger.debug("[%s] Stream loop started", self.serial)
        while not self._stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(
                    reader.read(settings.video_chunk_size),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.warning("[%s] Video read error: %s", self.serial, exc)
                break

            if not chunk:
                logger.info("[%s] Video stream closed by device", self.serial)
                break

            await self._broadcast(chunk)

        logger.debug("[%s] Stream loop ended", self.serial)

    async def _broadcast(self, chunk: bytes) -> None:
        """Send a chunk to all connected clients; remove dead clients silently."""
        if not self._clients:
            return

        # Take a snapshot once — the set must not change between gather and zip
        snapshot = list(self._clients)
        results = await asyncio.gather(
            *[ws.send_bytes(chunk) for ws in snapshot],
            return_exceptions=True,
        )
        for ws, result in zip(snapshot, results):
            if isinstance(result, Exception):
                self._clients.discard(ws)
                logger.debug("[%s] Removed disconnected client", self.serial)

    # ------------------------------------------------------------------
    # Internal: grace period & cleanup
    # ------------------------------------------------------------------

    def _schedule_grace_stop(self) -> None:
        if settings.session_grace_period <= 0:
            self._grace_task = asyncio.create_task(
                self.stop(), name=f"grace-{self.serial}"
            )
            return
        self._grace_task = asyncio.create_task(
            self._grace_stop(), name=f"grace-{self.serial}"
        )

    async def _grace_stop(self) -> None:
        logger.debug(
            "[%s] Grace period started (%.0fs)", self.serial, settings.session_grace_period
        )
        await asyncio.sleep(settings.session_grace_period)
        if not self._clients:
            logger.info("[%s] Grace period expired, stopping session", self.serial)
            await self.stop()

    def _cancel_grace_timer(self) -> None:
        if self._grace_task and not self._grace_task.done():
            self._grace_task.cancel()
            self._grace_task = None

    async def _cleanup(self) -> None:
        """Close sockets, kill the ADB process, and release the port."""
        for writer in (self._control_writer, self._video_writer):
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        self._control_writer = None
        self._video_writer = None
        self._video_reader = None

        if self._adb_process:
            try:
                self._adb_process.terminate()
                await asyncio.wait_for(self._adb_process.wait(), timeout=3.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    self._adb_process.kill()
                except ProcessLookupError:
                    pass
            self._adb_process = None

        if self._port:
            await self._adb.remove_forward(self.serial, self._port)
            await self._ports.release(self._port)
            self._port = 0

    async def _notify_clients_disconnected(self) -> None:
        for ws in list(self._clients):
            try:
                await ws.send_json({"event": "device_disconnected", "serial": self.serial})
            except Exception:
                pass
        self._clients.clear()
