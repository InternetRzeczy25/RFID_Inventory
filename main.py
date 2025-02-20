import asyncio
import logging
import os
import sys
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from server.utils.parser import keonn_revents_stream

import aiomqtt
from dotenv import load_dotenv
from tortoise import Tortoise, run_async

from server.models import (
    Event,
    Location,
    Tag,
    TagEvent,
    EventType,
    TagStatus,
    MQTT_Message,
)

load_dotenv()


fmt = logging.Formatter(
    fmt="%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
sh.setFormatter(fmt)

# will print debug sql
logger_db_client = logging.getLogger("tortoise.db_client")
# logger_db_client.setLevel(logging.DEBUG)
logger_db_client.addHandler(sh)

logger = logging.getLogger("iot")
logging.basicConfig()
logger.setLevel(logging.DEBUG)

LOST_THRESHOLD = 5.0

KEON_MQTT_CONF = {
    # "hostname": "127.0.0.1",
    "hostname": "192.168.0.102",
    "port": 1883,
    "identifier": "server",
}


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
        await asyncio.sleep(5.0)


async def event_sink():
    while True:
        evts: list[TagEvent] = await equeue.get()
        logger.info(f"TagEvents: {evts}")
        await Event.bulk_create(
            [Event(tag=e.tag, type=e.type, data=e.data) for e in evts]
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
                    )
                    tevents.append(
                        TagEvent(type=EventType.TAG_ADDED, tag=ntag, data={})
                    )
            if tevents:
                await equeue.put(tevents)


async def main():
    await Tortoise.init(
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["models"]},
    )
    await Tortoise.generate_schemas(safe=True)
    await asyncio.gather(
        monitor_lost(),
        process_kmqtt(),
        event_sink(),
    )


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    run_async(main())
