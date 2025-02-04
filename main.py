import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum
from parser import keonn_revents_stream
from typing import Any

import aiomqtt
from dotenv import load_dotenv
from tortoise import Tortoise, run_async

from models import Tag, TagStatus

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

LOST_THRESHOLD = 5.0

KEON_MQTT_CONF = {
    "hostname": "172.26.226.211",
    "port": 1883,
    "identifier": "server",
}

NOTIFIER_MQTT_CONF = {
    "hostname": "172.26.226.211",
    "port": 1883,
    "identifier": "notifier",
}

# monitoring LOST
# events sink
# processing


class TagEventType(IntEnum):
    TAG_LOST = 0
    TAG_LOC_CHANGE = 1
    TAG_ADDED = 2
    TAG_REAPPEARED = 3


@dataclass
class TagEvent:
    type: TagEventType
    tag_id: int
    data: dict[Any, Any] | list[Any]


equeue = asyncio.Queue()


async def monitor_lost():
    while True:
        dtime = datetime.now(timezone.utc) - timedelta(seconds=LOST_THRESHOLD)
        qlost = (
            Tag.filter(last_active_at__lte=dtime).exclude(status=TagStatus.LOST).all()
        )
        lost = await qlost
        print(f"{lost=}")
        # Update status in DB to LOST in single query
        await qlost.update(status=TagStatus.LOST)
        await equeue.put(
            [TagEvent(type=TagEventType.TAG_LOST, tag_id=t._id, data={}) for t in lost]
        )
        await asyncio.sleep(5.0)


async def event_sink():
    while True:
        evts: list[TagEvent] = await equeue.get()
        print(f"{evts=}")


async def main():
    await Tortoise.init(
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["models"]},
    )
    await Tortoise.generate_schemas(safe=True)

    # async with aiomqtt.Client(**KEON_MQTT_CONF) as kmqtt:
    #     await kmqtt.subscribe("RFID/devices")

    #     async for revents in keonn_revents_stream(kmqtt.messages):
    #         # Process ReadEvents
    #         pass

    await asyncio.gather(monitor_lost(), event_sink())


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    run_async(main())
