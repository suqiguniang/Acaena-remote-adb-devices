import asyncio

from app.config import settings


class PortAllocator:
    """Thread-safe pool of TCP ports for ADB forwarding.

    Each ScrcpySession acquires one port on start and releases it on stop.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._available: set[int] = set(
            range(settings.port_range_start, settings.port_range_end + 1)
        )

    async def acquire(self) -> int:
        """Return a free port. Raises RuntimeError if the pool is exhausted."""
        async with self._lock:
            if not self._available:
                raise RuntimeError(
                    f"Port pool exhausted — all ports {settings.port_range_start}–"
                    f"{settings.port_range_end} are in use. "
                    "Increase port_range_end or disconnect unused devices."
                )
            return self._available.pop()

    async def release(self, port: int) -> None:
        """Return a port to the pool."""
        async with self._lock:
            self._available.add(port)

    @property
    def available_count(self) -> int:
        return len(self._available)
