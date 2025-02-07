from fastapi import APIRouter, FastAPI
from fastapi_proxy_lib.core.http import ReverseHttpProxy
from fastapi_proxy_lib.core.websocket import ReverseWebSocketProxy
from fastapi_proxy_lib.fastapi.router import RouterHelper
from httpx import AsyncClient

keonn_ip = "192.168.7.2"
keonn_http = f"http://{keonn_ip}/"
keonn_ws = f"ws://{keonn_ip}:11987/"

helper = RouterHelper()
app = FastAPI(lifespan=helper.get_lifespan())

reverse_http_router = None
reverse_ws_router = None
ws_proxy = None


@app.get("/remove")
async def handler():
    await ws_proxy.aclose()
    app.router.routes = [
        r
        for r in app.routes
        if r not in (*reverse_ws_router.routes, *reverse_http_router.routes)
    ]
    return "Removed"


@app.get("/add")
async def handler2():
    global reverse_http_router, reverse_ws_router, ws_proxy

    reverse_http_router = helper.register_router(
        ReverseHttpProxy(base_url=keonn_http, follow_redirects=True),
        APIRouter(prefix="/device1"),
    )

    ws_proxy = ReverseWebSocketProxy(AsyncClient(), base_url=keonn_ws)
    reverse_ws_router = helper.register_router(ws_proxy)

    app.include_router(reverse_http_router)
    app.include_router(reverse_ws_router)
    return "OK"
