import urllib.parse
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.device_registry import registry

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    devices = registry.list_devices()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "devices": devices},
    )


@router.get("/api/devices")
async def api_devices() -> list[dict[str, Any]]:
    return [d.model_dump() for d in registry.list_devices()]


@router.get("/api/devices/{serial:path}")
async def api_device(serial: str) -> dict[str, Any]:
    device = registry.get_device(serial)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    session = registry.get_session(serial)
    result = device.model_dump()
    result["session_state"] = session.state.value if session else "idle"
    return result


@router.get("/{serial:path}", response_class=HTMLResponse)
async def device_page(request: Request, serial: str) -> HTMLResponse:
    device = registry.get_device(serial)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found or not connected")

    return templates.TemplateResponse(
        "device.html",
        {
            "request": request,
            "serial": serial,
            "serial_encoded": urllib.parse.quote(serial, safe=""),
            "model": device.model,
        },
    )
