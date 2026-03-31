# Acaena — Remote ADB Devices

<p align="center">
  <img src="static/img/logo.png" alt="Acaena logo" width="180"/>
</p>

Web panel for remote Android device management via [scrcpy](https://github.com/Genymobile/scrcpy).
Access any connected device at `http://your-server/<serial_number>`.

## Features

- Full remote control — clicks, swipes, keyboard input
- Multi-device support — connect to any number of devices simultaneously
- URL-based routing — `example.com/<serial>` per device
- Auto device discovery — detects ADB devices on connect/disconnect
- Minimal stack — Python + tiny JS frontend, no Node.js build step

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- ADB installed and in `PATH`
- Android device with USB debugging enabled

## Quick Start

```bash
# Clone
git clone https://github.com/yourusername/remote-adb-panel
cd remote-adb-panel

# Install dependencies
uv sync

# Copy config
cp .env.example .env

# Download scrcpy-server (version must match SCRCPY_VERSION in .env)
# https://github.com/Genymobile/scrcpy/releases — grab scrcpy-server from assets
# Place the file as ./scrcpy-server

# Run
uv run main.py
```

Open `http://localhost:8000` — connected devices will appear automatically.

## Docker

```bash
cp .env.example .env
docker compose up
```

> For USB-connected devices, see the commented section in `docker-compose.yml`.
> WiFi ADB (`adb connect <ip>:<port>`) works out of the box.

## Development

```bash
uv sync
uv run pre-commit install
uv run main.py
```

## Architecture

```
Browser
  └── WebSocket /ws/<serial>  ←→  ScrcpySession
                                       ├── video: TCP → H.264 → WS → jmuxer → <video>
                                       └── control: WS → TCP → ADB forward → device
```

Each device gets its own `ScrcpySession` with an isolated TCP port.
The `DeviceRegistry` polls `adb devices` every 3 seconds and manages session lifecycles.

## License

MIT
