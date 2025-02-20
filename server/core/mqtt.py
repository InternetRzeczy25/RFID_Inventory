import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone

import aiomqtt

from server.core import KEON_MQTT_CONF, LOST_THRESHOLD
from server.core.parser import keonn_revents_stream
from server.models import (
    Event,
    EventType,
    Location,
    Tag,
    TagEvent,
    TagStatus,
)

logger = logging.getLogger("iot")
logger.setLevel(logging.DEBUG)


equeue = asyncio.Queue()


async def monitor_lost():
    while True:
        dtime = datetime.now(timezone.utc) - timedelta(seconds=LOST_THRESHOLD)
        qlost = (
            Tag.filter(last_active_at__lte=dtime).exclude(status=TagStatus.LOST).all()
        )
        lost = await qlost
        # Update status in DB to LOST in single query
        await qlost.update(status=TagStatus.LOST)
        if lost:
            tevents = [TagEvent(type=EventType.TAG_LOST, tag=t, data={}) for t in lost]
            await equeue.put(tevents)
        await asyncio.sleep(LOST_THRESHOLD)


async def event_sink():
    while True:
        evts: list[TagEvent] = await equeue.get()
        logger.info(f"TagEvents: {evts}")
        await Event.bulk_create(
            [Event(tag=e.tag, type=e.type, data=e.data, notified=False) for e in evts]
        )


async def process_kmqtt():
    async with aiomqtt.Client(**KEON_MQTT_CONF) as kmqtt:
        logger.info(f"Keonn MQTT connected to broker at {KEON_MQTT_CONF['hostname']}")
        await kmqtt.subscribe("RFID/devices")

        async for revents in keonn_revents_stream(kmqtt.messages):
            tags = (
                await Tag.filter(epc__in=[e.epc for e in revents])
                .prefetch_related("last_loc_seen")
                .all()
            )
            locobjs = await Location.filter(id__in=[e.location for e in revents]).all()

            tevents = []
            for e in revents:
                dbtag, mloc = None, None
                with suppress(StopIteration):
                    dbtag = next(filter(lambda t: t.epc == e.epc, tags))
                with suppress(StopIteration):
                    mloc = next(filter(lambda lo: lo.id == e.location, locobjs))

                if not mloc:
                    logger.error(f"No object in db for location '{e.location}'!")

                if dbtag:
                    # Tag exists in DB
                    if dbtag.status == TagStatus.LOST:
                        tevents.append(
                            TagEvent(
                                type=EventType.TAG_REAPPEARED,
                                tag=dbtag,
                                data={},
                            )
                        )

                    if dbtag.last_loc_seen and dbtag.last_loc_seen.id != e.location:
                        tevents.append(
                            TagEvent(
                                type=EventType.TAG_LOC_CHANGE,
                                tag=dbtag,
                                data={
                                    "from": dbtag.last_loc_seen.id,
                                    "to": e.location,
                                },
                            )
                        )

                    dbtag.last_loc_seen = mloc
                    dbtag.last_active_at = datetime.now(timezone.utc)
                    dbtag.status = TagStatus.ACTIVE
                    await dbtag.save()
                else:
                    # Tag doesnt exist in DB
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
                await equeue.put(tevents)
