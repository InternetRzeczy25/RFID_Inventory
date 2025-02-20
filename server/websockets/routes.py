from fastapi import APIRouter, WebSocket
from server.models import MQTT_Message
from uuid import uuid4
import asyncio
from starlette.responses import FileResponse
import pathlib as pl

router = APIRouter(tags=["Websockets"])

connections = {}


@router.get("/chat")
async def chat():
    paf = pl.Path(__file__).parent / "chat.html"
    return FileResponse(paf)


@router.websocket("/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    id = str(uuid4())
    connections[id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            for connection in connections.values():
                await connection.send_text(f"{id}: {data}")
    except Exception:
        del connections[id]
        await websocket.close()


@router.websocket("/mqtt")
async def ws_mqtt(websocket: WebSocket):
    await websocket.accept()

    def pass_message(message: MQTT_Message):
        websocket.send_json(message.model_dump())

    try:
        while True:
            await asyncio.sleep(0.1)
    except Exception:
        await websocket.close()
