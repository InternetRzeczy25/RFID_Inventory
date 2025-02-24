import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from server.models import EventType, MQTT_Message
from server.api import api_v1, api_v2
from server.utils.proxy_fastapi import router as proxy_router
from server.websockets import router as ws_router
import httpx

load_dotenv()


def create_app(**app_kwargs) -> FastAPI:
    app = FastAPI(
        title="RFID Inventory System",
        version="0.1.0",
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["http://172.26.224.13"],
                allow_methods=["*"],
            )
        ],
        **app_kwargs,
    )

    @app.exception_handler(httpx.RequestError)
    async def handle_forward_errors(request: Request, e: httpx.RequestError):
        code = 504 if issubclass(e.__class__, httpx.TimeoutException) else 502

        return JSONResponse(
            {"detail": [{"msg": str(e), "type": e.__class__.__name__}]},
            status_code=code,
        )

    app.include_router(api_v1, prefix="/api/v1")
    app.include_router(api_v2, prefix="/api/v2")

    app.include_router(ws_router, prefix="/ws")
    app.include_router(proxy_router)

    @app.get("/mqtt/schema", response_model=MQTT_Message, tags=["Utilities"])
    async def get_mqtt():
        return MQTT_Message(
            action=EventType.TAG_LOST,
            loc_id=1,
            past_loc_id=1,
            event_id=1,
            tag_id=1,
        )

    register_tortoise(
        app,
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["server.models"]},
        generate_schemas=True,
    )

    return app
