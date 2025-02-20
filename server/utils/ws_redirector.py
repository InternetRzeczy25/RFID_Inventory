from fastapi import FastAPI, WebSocket
from fastapi_proxy_lib.core.websocket import ReverseWebSocketProxy
from httpx import AsyncClient
from typing import AsyncIterator
from pydantic import BaseModel
from contextlib import asynccontextmanager


app = FastAPI()

proxies: dict[str, ReverseWebSocketProxy] = {}


@asynccontextmanager
async def close_proxy_event(_: FastAPI) -> AsyncIterator[None]:
    """Close proxy."""
    yield
    for proxy in proxies.values():
        await proxy.aclose()


app = FastAPI(lifespan=close_proxy_event)


@app.websocket("/")
async def _(ws: WebSocket):
    await ws.accept()
    redirect_name = ws.cookies.get("ws_redirect")
    if redirect_name not in proxies:
        return await ws.close()
    return await proxies[redirect_name].proxy(websocket=ws)


class IP(BaseModel):
    ip: str
    redirect_name: str


@app.post("/paths")
async def update_ip(request: IP):
    global proxy
    if request.redirect_name in proxies:
        await proxies[
            request.redirect_name
        ].aclose()  # force reload of existing connections

    proxies[request.redirect_name] = ReverseWebSocketProxy(
        AsyncClient(), base_url=f"ws://{request.ip}:11987/"
    )
    return "Updated"


# @app.websocket("/")
# async def websocket_redirect(websocket: WebSocket):
#     cookie_value = websocket.cookies.get("ws_redirect", "ws://127.0.0.1:5000/device1")
#     resp = RedirectResponse(f"ws://{cookie_value}")
#     await websocket.send_denial_response(resp)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=11987)
