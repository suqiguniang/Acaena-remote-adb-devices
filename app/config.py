from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # ADB
    adb_path: str = "adb"
    adb_poll_interval: float = 3.0

    # scrcpy
    scrcpy_server_path: str = "scrcpy-server"
    scrcpy_server_device_path: str = "/data/local/tmp/scrcpy-server.jar"
    scrcpy_version: str = "3.1"
    video_bitrate: int = 2_000_000

    # Port range for ADB forwarding — one port per connected device
    port_range_start: int = 27183
    port_range_end: int = 27199

    # Grace period (seconds) before stopping a session when the last client disconnects
    session_grace_period: float = 30.0

    # Socket connection retry settings for scrcpy-server startup
    socket_connect_retries: int = 10
    socket_connect_delay: float = 0.2

    # Video chunk size when reading from the TCP stream
    video_chunk_size: int = 20480


settings = Settings()
