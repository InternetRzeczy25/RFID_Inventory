import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from tortoise import Tortoise, run_async

from models import Device, Location, Tag, TagStatus

load_dotenv()


async def seed_tags():
    await Tag.create(
        epc="e28011700000020f7cbd7358",
        RSSI=-20,
        last_active_at=datetime.now(timezone.utc),
        status=TagStatus.ACTIVE,
        name="Oscyloskop",
    )
    await Tag.create(
        epc="0000000deadbeef",
        RSSI=-20,
        last_active_at=datetime.now(timezone.utc),
        status=TagStatus.ACTIVE,
        name="Radziecki przyrząd",
    )


async def seed_devices():
    await Device.create(
        last_active_at=datetime.now(timezone.utc),
        name="TMS",
        mac="60:e8:5b:0a:78:5f",
        ip="123.456.789.000",
        online=True,
        meta={},
    )


async def seed_locations():
    await Location.create(
        _id="60:e8:5b:0a:78:5f/1/0/0", name="Lodex 314", device=(await Device.first())
    )


async def main():
    await Tortoise.init(
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["models"]},
    )
    try:
        await seed_devices()
    except Exception:
        print(e)

    try:
        await seed_locations()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    run_async(main())
