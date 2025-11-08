from enum import Enum
from typing import Literal

from pydantic import BaseModel


class SessionState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    STREAMING = "streaming"
    STOPPING = "stopping"
    ERROR = "error"


class DeviceInfo(BaseModel):
    serial: str
    state: Literal["device", "offline", "unauthorized"]
    model: str
