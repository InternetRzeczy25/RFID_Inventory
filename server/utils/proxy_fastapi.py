import asyncio
from contextlib import asynccontextmanager
from typing import TypeVar

from fastapi import APIRouter, FastAPI, Request, WebSocket
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi_proxy_lib.core.http import ReverseHttpProxy
from fastapi_proxy_lib.core.websocket import ReverseWebSocketProxy
from fastapi_proxy_lib.core._tool import check_base_url
from httpx import AsyncClient, DigestAuth


from server.logging import get_configured_logger
from server.models import Device

logger = get_configured_logger(__name__, "DEBUG")
logger.handlers[0].setLevel("WARNING")

http_proxies: dict[int, ReverseHttpProxy] = {}
ws_proxies: dict[int, ReverseWebSocketProxy] = {}


class AuthedClient(AsyncClient):
    def __init__(
        self,
    ):
        super().__init__(auth=DigestAuth("admin", "admin"))


http_client = AuthedClient()


@asynccontextmanager
async def proxy_lifespan(app: FastAPI):
    yield
    logger.debug(f"Closing {len(ws_proxies) + 1} proxy clients")
    await asyncio.gather(
        *(proxy.aclose() for proxy in (http_client, *ws_proxies.values()))
    )


router = APIRouter(lifespan=proxy_lifespan, prefix="/proxy", tags=["Proxy"])

T = TypeVar("T", bound=ReverseHttpProxy | ReverseWebSocketProxy)


async def get_proxy(device_id: int, proxies: dict[int, T]) -> T:
    if device_id not in proxies:
        ip = await Device.get_or_none(id=device_id).values_list("ip", flat=True)
        if ip is None:
            logger.error(f"Device {device_id=} not found in the database!")
            raise HTTPException(status_code=404, detail="Device not found")
        if proxies is http_proxies:
            logger.debug(f"Creating new http proxy for {device_id=}, {ip=}")
            proxies[device_id] = ReverseHttpProxy(
                http_client, base_url=f"http://{ip}/", follow_redirects=True
            )
        else:
            logger.debug(f"Creating new websocket proxy for {device_id=}, {ip=}")
            proxies[device_id] = ReverseWebSocketProxy(
                AuthedClient(), base_url=f"ws://{ip}:11987/", follow_redirects=True
            )
    return proxies[device_id]


async def update_ip(device_id: int, ip: str):
    global http_proxies, ws_proxies
    logger.debug(f"Updating {device_id=} to {ip=}")
    if device_id in http_proxies:
        http_proxies[device_id].base_url = check_base_url(f"http://{ip}/")
    if device_id in ws_proxies:
        await ws_proxies[device_id].aclose()  # force reload of existing connections
        ws_proxies[device_id] = ReverseWebSocketProxy(
            AuthedClient(), base_url=f"ws://{ip}:11987/", follow_redirects=True
        )
    return True


async def __replace_in_file_response(response: StreamingResponse, old: str, new: str):
    old_content = response.body_iterator
    nc = "".join([x.decode("utf-8") async for x in old_content])
    nc = nc.replace(old, new)
    logger.debug(f"Replacing {old=} to {new=}")
    new_resp = StreamingResponse(
        content=iter([nc]),
        status_code=response.status_code,
        headers=response.headers.update({"Content-Length": str(len(nc))}),
        media_type=response.media_type,
    )
    return new_resp


@router.get("/{device_id:int}/js/core.js")
async def _(request: Request, device_id: int):
    # HACK: Updating the hardcoded websocket address lets us proxy the
    # websocket connection in the same app without proxying the 11987 port
    proxy = await get_proxy(device_id, http_proxies)
    proxy_response = await proxy.proxy(request=request, path="js/core.js")
    if isinstance(proxy_response, StreamingResponse):
        new_websocket = f"{request.url.netloc}{router.prefix}/ws/{device_id}"
        return await __replace_in_file_response(
            proxy_response, "${Device.IP}:11987", new_websocket
        )

    return proxy_response


@router.get("/{device_id:int}/js/utils/REST.js")
async def _(request: Request, device_id: int):
    proxy = await get_proxy(device_id, http_proxies)
    proxy_response = await proxy.proxy(request=request, path="js/utils/REST.js")
    if isinstance(proxy_response, StreamingResponse):
        address = f"{request.url.netloc}{router.prefix}/{device_id}"
        return await __replace_in_file_response(
            proxy_response, "${this.baseUrl}", address
        )

    return proxy_response


paf = "/{device_id:int}/{path:path}"
kwargs = {}


@router.get("/{device_id:int}")
async def _(device_id: int, request: Request):
    return RedirectResponse(f"{request.url}/index.html")


# based on fastapi_proxy_lib.fastapi.router._http_register_router
@router.get(paf, **kwargs)
@router.post(paf, **kwargs)
@router.put(paf, **kwargs)
@router.delete(paf, **kwargs)
@router.options(paf, **kwargs)
@router.head(paf, **kwargs)
@router.patch(paf, **kwargs)
@router.trace(paf, **kwargs)
async def http_proxy(device_id: int, path: str, request: Request):
    proxy = await get_proxy(device_id, http_proxies)
    return await proxy.proxy(request=request, path=path)


@router.websocket("/ws/{device_id:int}")
@router.websocket("/ws/{device_id:int}/{path:path}")
async def ws_proxy(websocket: WebSocket, device_id: int, path: str = ""):
    proxy = await get_proxy(device_id, ws_proxies)
    logger.debug(f"WS: {device_id=}, {path=}, {websocket.base_url=}")
    return await proxy.proxy(websocket=websocket, path=path)
