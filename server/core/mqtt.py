import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone

import aiomqtt

from server.core import KEONN_BROKER_CONF, LOST_THRESHOLD
from server.core.parser import keonn_revents_stream
from server.logging import get_configured_logger
from server.models import (
    Event,
    EventType,
    Location,
    Tag,
    TagEvent,
    TagStatus,
)

logger = get_configured_logger(__name__, "DEBUG")

equeue = asyncio.Queue()


async def monitor_lost():
    await asyncio.sleep(5)
    while True:
        try:
            dtime = datetime.now(timezone.utc) - timedelta(seconds=LOST_THRESHOLD)
            qlost = (
                Tag.filter(last_active_at__lte=dtime)
                .exclude(status=TagStatus.LOST)
                .prefetch_related("last_loc_seen")
                .all()
            )
            lost = await qlost
            # Update status in DB to LOST in single query
            logger.debug(
                f"Marked {await qlost.update(status=TagStatus.LOST)} tags as LOST"
            )
            if lost:
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
                await equeue.put(tevents)
            await asyncio.sleep(LOST_THRESHOLD)
        except Exception as e:
            logger.exception(str(e))


async def event_sink():
    while True:
        try:
            evts: list[TagEvent] = await equeue.get()
            await Event.bulk_create(
                [
                    Event(tag=e.tag, type=e.type, data=e.data, notified=False)
                    for e in evts
                ]
            )
            logger.info(f"Added {len(evts)} events")
        except Exception as e:
            logger.exception(str(e))


async def process_kmqtt():
    async with aiomqtt.Client(**KEONN_BROKER_CONF, identifier="processor") as kmqtt:
        logger.info(
            f"Keonn MQTT connected to broker at {KEONN_BROKER_CONF['hostname']}"
        )
        await kmqtt.subscribe("RFID/devices")

        async for revents in keonn_revents_stream(kmqtt.messages):
            try:
                tags = (
                    await Tag.filter(epc__in=[e.epc for e in revents])
                    .prefetch_related("last_loc_seen")
                    .all()
                )
                locobjs = await Location.filter(
                    loc__in=[e.location for e in revents]
                ).all()

                tevents = []
                for e in revents:
                    dbtag, mloc = None, None
                    with suppress(StopIteration):
                        dbtag = next(filter(lambda t: t.epc == e.epc, tags))
                    with suppress(StopIteration):
                        mloc = next(filter(lambda lo: lo.loc == e.location, locobjs))

                    if not mloc:
                        logger.error(f"No object in db for location '{e.location}'!")

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
                    await equeue.put(tevents)
            except Exception as e:
                logger.exception(str(e))
