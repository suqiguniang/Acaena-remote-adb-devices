import asyncio
import logging
import re

from app.config import settings
from app.models.device import DeviceInfo

logger = logging.getLogger(__name__)

# Matches a line like: "emulator-5554          device product:sdk_gphone model:sdk_gphone"
_DEVICE_LINE_RE = re.compile(
    r"^(?P<serial>\S+)\s+(?P<state>device|offline|unauthorized)"
    r"(?:.*\bmodel:(?P<model>\S+))?",
)


class AdbManager:
    """Async wrappers around ADB subprocess commands.

    All methods use asyncio.create_subprocess_exec so they never block
    the event loop. Each call targets a specific device via -s <serial>
    so all operations are fully parallel across devices.
    """

    async def list_devices(self) -> list[DeviceInfo]:
        """Return a list of currently connected ADB devices."""
        stdout = await self._run(settings.adb_path, "devices", "-l")
        devices: list[DeviceInfo] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            m = _DEVICE_LINE_RE.match(line)
            if m and m.group("state") in ("device", "offline", "unauthorized"):
                devices.append(
                    DeviceInfo(
                        serial=m.group("serial"),
                        state=m.group("state"),
                        model=m.group("model") or "unknown",
                    )
                )
        return devices

    async def push_server(self, serial: str) -> None:
        """Push the scrcpy-server JAR to the device."""
        await self._run(
            settings.adb_path,
            "-s", serial,
            "push",
            settings.scrcpy_server_path,
            settings.scrcpy_server_device_path,
        )
        logger.debug("[%s] scrcpy-server pushed", serial)

    async def forward_port(self, serial: str, local_port: int) -> None:
        """Set up ADB port forward: tcp:<local_port> -> localabstract:scrcpy."""
        await self._run(
            settings.adb_path,
            "-s", serial,
            "forward",
            f"tcp:{local_port}",
            "localabstract:scrcpy",
        )
        logger.debug("[%s] ADB forward tcp:%d -> scrcpy", serial, local_port)

    async def remove_forward(self, serial: str, local_port: int) -> None:
        """Remove the ADB port forward for a given port."""
        try:
            await self._run(
                settings.adb_path,
                "-s", serial,
                "forward",
                "--remove",
                f"tcp:{local_port}",
            )
        except Exception:
            pass  # best-effort cleanup; device may already be gone

    async def remove_all_forwards_in_range(self) -> None:
        """Remove all ADB forwards in the app's port range on startup."""
        try:
            stdout = await self._run(settings.adb_path, "forward", "--list")
        except Exception:
            return
        for line in stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith("tcp:"):
                try:
                    port = int(parts[1][4:])
                    if settings.port_range_start <= port <= settings.port_range_end:
                        serial = parts[0]
                        await self.remove_forward(serial, port)
                        logger.info("Cleaned up stale forward: %s tcp:%d", serial, port)
                except ValueError:
                    pass

    async def start_server(self, serial: str) -> asyncio.subprocess.Process:
        """Launch scrcpy-server on the device via adb shell.

        Returns the subprocess handle so the caller can kill it on shutdown.
        stdout/stderr are discarded — keeping PIPE but never reading would fill
        the OS buffer (~64 KB) and stall the process mid-stream.
        """
        cmd = [
            settings.adb_path, "-s", serial, "shell",
            f"CLASSPATH={settings.scrcpy_server_device_path}",
            "app_process",
            "/",
            "com.genymobile.scrcpy.Server",
            settings.scrcpy_version,
            "tunnel_forward=true",
            f"video_bit_rate={settings.video_bitrate}",
            "audio=false",
            "control=true",
            "cleanup=false",
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        logger.debug("[%s] scrcpy-server process started (pid=%d)", serial, process.pid)
        return process

    # --- helpers ---

    async def _run(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f"ADB command {args!r} failed (rc={process.returncode}): "
                f"{stderr.decode().strip()}"
            )
        return stdout.decode()
