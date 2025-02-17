from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse
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
http_proxy = None
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


@app.get("/{device:path}/js/core.js")
async def _(request: Request, device: str):
    proxy_response = await http_proxy.proxy(request=request, path="js/core.js")
    if isinstance(proxy_response, StreamingResponse):
        old_content = proxy_response.body_iterator

        nc = "".join([x.decode("utf-8") async for x in old_content])
        nc = nc.replace("${Device.IP}:11987", f"127.0.0.1/{device}/")

        new_resp = StreamingResponse(
            content=iter([nc]),
            status_code=proxy_response.status_code,
            headers=proxy_response.headers,
            media_type=proxy_response.media_type,
        )
        new_resp.headers["Content-Length"] = str(len(nc))
        return new_resp
    return proxy_response


@app.get("/add")
async def handler2():
    global reverse_http_router, reverse_ws_router, http_proxy, ws_proxy

    http_proxy = ReverseHttpProxy(base_url=keonn_http, follow_redirects=True)
    reverse_http_router = helper.register_router(
        http_proxy,
        APIRouter(prefix="/device1"),
    )

    ws_proxy = ReverseWebSocketProxy(
        AsyncClient(), base_url=keonn_ws, follow_redirects=True
    )
    reverse_ws_router = helper.register_router(ws_proxy, APIRouter(prefix="/device1"))

    app.include_router(reverse_http_router)
    app.include_router(reverse_ws_router)
    return "OK"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=80)
