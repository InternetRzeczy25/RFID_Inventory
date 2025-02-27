import asyncio
import ipaddress
from collections.abc import Callable, Coroutine
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from functools import wraps

import aiomqtt

from server.core import KEONN_BROKER_CONF, LOST_THRESHOLD
from server.core.parser import keonn_revents_stream
from server.logging import get_configured_logger
from server.models import (
    Device,
    Event,
    EventType,
    Location,
    Tag,
    TagEvent,
    TagStatus,
)
from server.utils.proxy_fastapi import update_ip

logger = get_configured_logger(__name__, "DEBUG")

equeue = asyncio.Queue()

seconds = float


def loop(w8_after_exc: seconds = 1):
    def decorator(func: Callable[..., Coroutine]):
        @wraps(func)
        async def wrapper():
            while True:
                try:
                    await func()
                except asyncio.CancelledError:
                    break
                except aiomqtt.MqttError as e:
                    logger.error(f"MQTT error: {e}")
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.exception(str(e))
                    await asyncio.sleep(w8_after_exc)

        return wrapper

    return decorator


@loop(3)
async def monitor_lost():
    await asyncio.sleep(LOST_THRESHOLD)
    dtime = datetime.now(timezone.utc) - timedelta(seconds=LOST_THRESHOLD)
    qlost = (
        Tag.filter(last_active_at__lte=dtime)
        .exclude(status=TagStatus.LOST)
        .prefetch_related("last_loc_seen")
        .all()
    )
    lost = await qlost
    if lost:
        # Update status in DB to LOST in single query
        logger.debug(
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S')}: Marked {await qlost.update(status=TagStatus.LOST)} tags as LOST"
        )
        tevents = [
            TagEvent(
                type=EventType.TAG_LOST,
                tag=t,
                data={
                    "from": t.last_loc_seen and t.last_loc_seen.loc,
                    "RSSI": t.RSSI,
                },
            )
            for t in lost
        ]
        logger.debug(
            f"Adding {len(tevents)} lost events for tags {[tag.epc for tag in lost]}"
        )
        await equeue.put(tevents)


@loop()
async def event_sink():
    evts: list[TagEvent] = await equeue.get()
    await Event.bulk_create(
        [Event(tag=e.tag, type=e.type, data=e.data, notified=False) for e in evts]
    )
    logger.info(f"Sinking {len(evts)} events")


@loop()
async def process_kmqtt():
    async with aiomqtt.Client(**KEONN_BROKER_CONF, identifier="processor") as kmqtt:
        await kmqtt.subscribe("RFID/devices")

        logger.info(
            f"process_kmqtt connected to broker at {KEONN_BROKER_CONF['hostname']}"
        )

        async for revents in keonn_revents_stream(kmqtt.messages):
            tags = (
                await Tag.filter(epc__in=[e.epc for e in revents])
                .prefetch_related("last_loc_seen")
                .all()
            )
            locobjs = await Location.filter(loc__in=[e.location for e in revents]).all()

            tevents = []
            for e in revents:
                dbtag, mloc = None, None
                with suppress(StopIteration):
                    dbtag = next(filter(lambda t: t.epc == e.epc, tags))
                with suppress(StopIteration):
                    mloc = next(filter(lambda lo: lo.loc == e.location, locobjs))

                if not mloc:
                    logger.error(f"No object in db for location {(e.location)!r}!")

                if dbtag:
                    tag_loc = dbtag.last_loc_seen and dbtag.last_loc_seen.loc
                    # Tag exists in DB
                    if dbtag.status == TagStatus.LOST:
                        tevents.append(
                            TagEvent(
                                type=EventType.TAG_REAPPEARED,
                                tag=dbtag,
                                data={
                                    "from": tag_loc,
                                    "gone_for": (
                                        datetime.now(timezone.utc)
                                        - dbtag.last_active_at
                                    ).total_seconds(),
                                },
                            )
                        )
                        logger.debug(f"Tag {dbtag.epc} reappeared")

                    if tag_loc != e.location:
                        tevents.append(
                            TagEvent(
                                type=EventType.TAG_LOC_CHANGE,
                                tag=dbtag,
                                data={
                                    "from": tag_loc,
                                    "to": e.location,
                                },
                            )
                        )
                        logger.debug(f"Tag {dbtag.epc} moved")

                    dbtag.last_loc_seen = mloc
                    dbtag.last_active_at = datetime.now(timezone.utc)
                    dbtag.status = TagStatus.ACTIVE
                    await dbtag.save()
                else:
                    # Tag doesnt exist in DB
                    logger.debug(f"Adding tag: {e.epc}")
                    ntag = await Tag.create(
                        last_active_at=datetime.now(timezone.utc),
                        status=TagStatus.ACTIVE,
                        epc=e.epc,
                        RSSI=e.RSSI,
                        last_loc_seen=mloc,
                        name=e.epc,
                        description="",
                    )
                    tevents.append(
                        TagEvent(type=EventType.TAG_ADDED, tag=ntag, data={})
                    )
            if tevents:
                logger.debug(f"Adding {len(tevents)} events")
                await equeue.put(tevents)


@loop()
async def process_status():
    async with aiomqtt.Client(
        **KEONN_BROKER_CONF, identifier="status_processor"
    ) as kmqtt:
        await kmqtt.subscribe("RFID/status")

        logger.info(
            f"process_status connected to broker at {KEONN_BROKER_CONF['hostname']}"
        )

        async for msg in kmqtt.messages:
            mac, ip, status = msg.payload.decode().split(",")
            logger.debug(f"Ping from {mac=}, {ip=}, {status=}")
            dev = await Device.get_or_none(mac=mac)
            if dev is None:
                logger.error(f"process_status: unknown device {mac=}")
                continue
            if dev.ip != ip:
                logger.debug(f"New IP for device {dev.id}: {ip}")
                try:
                    ipaddress.ip_address(ip)
                    dev.ip = ip
                    await update_ip(dev.id, ip)
                except Exception as e:
                    logger.exception(e)
            dev.online = True
            dev.last_active_at = datetime.now(timezone.utc)
            await dev.save()
            logger.debug(f"Device {dev.id} updated!")
