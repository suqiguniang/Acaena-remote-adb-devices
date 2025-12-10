import asyncio
import logging

from app.config import settings
from app.core.adb_manager import AdbManager
from app.core.port_allocator import PortAllocator
from app.core.scrcpy_session import ScrcpySession
from app.models.device import DeviceInfo, SessionState

logger = logging.getLogger(__name__)


class DeviceRegistry:
    """Global singleton that tracks connected ADB devices and manages ScrcpySessions.

    Polls `adb devices` every adb_poll_interval seconds and fires connect/disconnect
    hooks. Sessions are started lazily — only when the first browser client connects.
    """

    def __init__(self) -> None:
        self._adb = AdbManager()
        self._ports = PortAllocator()
        self._sessions: dict[str, ScrcpySession] = {}
        self._known_devices: dict[str, DeviceInfo] = {}
        self._poll_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the ADB polling loop. Called from FastAPI lifespan."""
        await self._adb.remove_all_forwards_in_range()
        self._poll_task = asyncio.create_task(self._poll_loop(), name="adb-poll")
        logger.info("DeviceRegistry started")

    async def stop(self) -> None:
        """Stop polling and gracefully shut down all active sessions."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        for serial in list(self._sessions):
            await self._stop_session(serial)

        logger.info("DeviceRegistry stopped")

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def get_or_create_session(self, serial: str) -> ScrcpySession:
        """Return an existing running session, or start a new one.

        Raises KeyError if the serial is not in the known device list.
        """
        if serial not in self._known_devices:
            raise KeyError(f"Device '{serial}' is not connected")

        if serial not in self._sessions:
            self._sessions[serial] = ScrcpySession(serial, self._adb, self._ports)

        session = self._sessions[serial]
        if session.state in (SessionState.IDLE, SessionState.ERROR):
            await session.start()

        return session

    def get_session(self, serial: str) -> ScrcpySession | None:
        return self._sessions.get(serial)

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._known_devices.values())

    def get_device(self, serial: str) -> DeviceInfo | None:
        return self._known_devices.get(serial)

    # ------------------------------------------------------------------
    # Internal: polling
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while True:
            try:
                devices = await self._adb.list_devices()
                current_serials = {d.serial for d in devices if d.state == "device"}
                known_serials = set(self._known_devices)

                for device in devices:
                    if device.state == "device" and device.serial not in known_serials:
                        await self._on_device_connected(device)

                for serial in known_serials - current_serials:
                    await self._on_device_disconnected(serial)

            except Exception as exc:
                logger.warning("ADB poll error: %s", exc)

            await asyncio.sleep(settings.adb_poll_interval)

    async def _on_device_connected(self, device: DeviceInfo) -> None:
        self._known_devices[device.serial] = device
        logger.info("Device connected: %s (%s)", device.serial, device.model)

    async def _on_device_disconnected(self, serial: str) -> None:
        self._known_devices.pop(serial, None)
        logger.info("Device disconnected: %s", serial)
        await self._stop_session(serial)

    async def _stop_session(self, serial: str) -> None:
        session = self._sessions.pop(serial, None)
        if session:
            try:
                await session.stop()
            except Exception as exc:
                logger.error("[%s] Error stopping session: %s", serial, exc)


# Module-level singleton — imported by FastAPI lifespan and API handlers
registry = DeviceRegistry()
