import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.api.websocket import ws_router
from app.config import settings
from app.core.device_registry import registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await registry.start()
    yield
    await registry.stop()


app = FastAPI(title="Remote ADB Panel", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(ws_router)
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
