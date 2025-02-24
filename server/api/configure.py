from fastapi import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.params import Param
from tortoise.contrib.pydantic import pydantic_model_creator

from server.logging import get_configured_logger
from server.models import Device, Location
from server.utils.KEONN_interface import (
    API,
    Hz,
    beep,
    configure_keonn,
    device_info,
    get_info,
    get_locations,
    ms,
)

logger = get_configured_logger(__name__, "DEBUG")
logger.handlers[0].setLevel("DEBUG")
router = APIRouter(tags=["Configure"])


async def _get_ip(device_id: int):
    ip = await Device.get_or_none(id=device_id).values_list("ip", flat=True)
    if ip is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return ip


@router.post("/{device_id:int}/beep")
async def do_a_beep(
    device_id: int,
    f: Hz = Param(default=2000, description="Tone frequency"),
    t_on: ms = Param(100, description="Time on"),
    t_off: ms = Param(50, description="Time off"),
    d: ms = Param(450, description="Duration of the beep"),
):
    ip = await _get_ip(device_id)
    logger.debug(f"Beeping {ip=} {f=} {t_on=} {t_off=} {d=}")
    await beep(API(ip), None, f, t_on, t_off, d)
    return "Beeped"


@router.post("/{device_id:int}/write_config")
async def write_config(device_id: int):
    ip = await _get_ip(device_id)
    await configure_keonn(API(ip))
    return "Configured"


@router.get("/{device_id:int}/info")
async def get_device_info(device_id: int) -> device_info:
    ip = await _get_ip(device_id)
    return await get_info(API(ip))


pydantic_Locations = pydantic_model_creator(
    Location,
    name="Locations",
    include=("device_id", "id", "loc", "name", "created_at", "modified_at"),
)


@router.get("/{device_id:int}/locations")
async def get_device_locations(device_id: int) -> list[pydantic_Locations]:  # type: ignore
    logger.debug(f"Syncing locations for device {device_id}")
    ip = await _get_ip(device_id)
    locs = {loc: name for loc, name in (await get_locations(API(ip)))}
    logger.debug(f"Locations at {ip}: {locs}")
    dev_locs = set(
        await Location.filter(device_id=device_id).values_list("loc", flat=True)
    )
    logger.debug(f"Locations in the database: {dev_locs}")

    to_del = dev_locs - set(locs.keys())
    if to_del:
        logger.debug(f"Deleting {to_del=}")
        await Location.filter(loc__in=to_del).delete()

    for loc in set(locs.keys()) - dev_locs:
        name = locs[loc]
        await Location.create(loc=loc, name=name, device_id=device_id)
        logger.debug(f"Added {loc=}, {name=!r} to the database")

    return await pydantic_Locations.from_queryset(Location.filter(device_id=device_id))
