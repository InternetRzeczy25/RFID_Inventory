import asyncio
import logging
import os
import sys
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from server.core.parser import keonn_revents_stream

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
from server.core.mqtt import monitor_lost, process_kmqtt, event_sink

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


async def main():
    await Tortoise.init(
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["server.models"]},
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
