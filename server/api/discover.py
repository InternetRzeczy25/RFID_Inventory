import httpx
from fastapi.params import Param

from server.api._base import forward_exception
from server.api.device import Device, pydantic_batch_Device
from server.logging import get_configured_logger
from server.utils.KEONN_interface import API, get_info, get_metadata, make_sound
from server.utils.detect import KeonnFinder

logger = get_configured_logger(__name__, "DEBUG")

kf = KeonnFinder()


async def discover_devices(ip: str | None = Param(None)) -> list[pydantic_batch_Device]:  # type: ignore
    try:
        if ip is not None:
            logger.debug(f"Trying device at {(ip)!r}")
            device = API(ip)
            info = await get_info(device)
            meta = await get_metadata(device)
            await make_sound(device, meta.id)
            logger.debug(f"Found device {(meta.id)!r}")
            dev, added = await Device.get_or_create(
                mac=info.mac,
                defaults=dict(
                    ip=ip,
                    meta=meta.model_dump(),
                    online=True,
                    name=meta.id,
                ),
            )
            if not added:
                raise ValueError(f"Device {dev.name} already exists at this address!")
            logger.info(f"{dev.name} added!")
            return [await pydantic_batch_Device.from_tortoise_orm(dev)]

        # look for new devices
        await kf.run_detection()
        found = kf.get_devices()

        found_macs = set(found.keys())
        # get only macs from the database
        db_macs = await Device.filter(mac__in=found_macs).values_list("mac", flat=True)

        new_macs = found_macs - set(db_macs)

        if not new_macs:
            return []

        to_create = []
        for mac in new_macs:
            ip = found[mac]["ip"]
            device = API(ip)
            meta = await get_metadata(device)
            await make_sound(device, meta.id)
            to_create.append(
                Device(
                    mac=mac,
                    ip=ip,
                    meta=meta.model_dump(),
                    online=True,
                    name=meta.id,
                )
            )

        await Device.bulk_create(to_create)
        return await pydantic_batch_Device.from_queryset(
            Device.filter(mac__in=new_macs).all()
        )

    except Exception as e:
        if issubclass(type(e), httpx.RequestError):
            e: httpx.RequestError
            e.args = (f"{e.request.method} request to {e.request.url.host} failed!",)
        logger.exception(str(e))
        forward_exception(e, ip)
