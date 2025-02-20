import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from tortoise import Tortoise, run_async
from tortoise.transactions import in_transaction
from tortoise.exceptions import IntegrityError
from server.models import Device, Location, Tag, TagStatus, Event, EventType
import random
from itertools import product

load_dotenv()


async def seed_tags(num_tag_groups: int = 5):
    locs = await Location.all()
    assert locs, "No locations in the database!"
    for i, dev in product(
        range(num_tag_groups),
        (
            "Oscyloskop",
            "Radziecki przyrząd",
            "Monitor",
            "Zasilacz",
            "Kąkuter",
            "SDR",
        ),
    ):
        status = random.choice((TagStatus.ACTIVE, TagStatus.LOST))
        if status == TagStatus.LOST:
            delta = timedelta(hours=random.randint(0, 20), days=random.randint(0, 10))
        else:
            delta = timedelta(seconds=0)
        await Tag.create(
            epc=hex(random.getrandbits(24 * 4))[2:],
            RSSI=random.randint(-70, -20),
            last_active_at=datetime.now(timezone.utc) - delta,
            name=f"{dev} {i}",
            description="",
            status=status,
            last_loc_seen=random.choice((*locs, None)),
        )


async def seed_devices(num_devs: int = 5):
    for i in range(num_devs):
        mac_hex = hex(random.getrandbits(12 * 4))[2:]
        serial = random.randint(999, 9999)
        await Device.create(
            last_active_at=datetime.now(timezone.utc),
            name=f"Kełon {i}",
            mac=":".join(mac_hex[i : i + 2] for i in range(0, len(mac_hex), 2)),
            ip=f"192.168.1.{i}",
            online=True,
            meta={
                "id": f"AdvanPay-cf-eu-120-{mac_hex[-4:]}",
                "family": f"AdvanPay-cf-eu-120-{mac_hex[-4:]}",
                "serial": f"{serial:07}::{mac_hex}",
                "code": f"ADPY-EU-120 ({serial:07})",
                "fw_version": "3.0",
                "rf_module": "M6e-Nano::M6e Nano::30.00.00.02",
            },
        )


async def seed_locations(num_locs: int = 5):
    devs = await Device.all()
    assert devs, "No devices in the database!"
    for i in range(num_locs):
        dev = random.choice(devs)
        loc = "/".join(map(str, random.choices([*range(4)], k=3)))
        try:
            await Location.create(loc=f"{dev.mac}/{loc}", name=f"Półka {i}", device=dev)
        except IntegrityError:
            continue


async def seed_events(num_events: int = 10):
    for tag in (await Tag.first(), await Tag.last()):
        assert tag, "No tags in the database!"
        for i in range(num_events):
            typ = random.choice(list(EventType))
            data = {
                "from": f"{i}/{i}/{i}",
                "to": f"{i + 1}/{i + 1}/{i + 1}",
            }
            await Event.create(
                type=typ,
                data=data,
                created_at=datetime.now(timezone.utc),
                tag=tag,
                notified=random.choice((True, False)),
            )


async def main():
    await Tortoise.init(
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["server.models"]},
    )
    await Tortoise._drop_databases()
    await Tortoise.init(
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["server.models"]},
    )
    await Tortoise.generate_schemas(safe=False)
    # try:
    async with in_transaction():
        await seed_devices(5)
        await seed_locations(40)
        await seed_tags(50)
        await seed_events(4)
    print("Seed planted.")
    # except Exception as e:
    #     print(e)


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    run_async(main())
