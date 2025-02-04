import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from tortoise import Tortoise, run_async

from models import Tag, TagStatus

load_dotenv()


async def main():
    await Tortoise.init(
        db_url=os.environ.get("DB_CONNECTION_STRING"),
        modules={"models": ["models"]},
    )

    await Tag.create(
        epc="e28011700000020f7cbd7358",
        RSSI=-20,
        last_active_at=datetime.now(timezone.utc),
        status=TagStatus.ACTIVE,
        name="Oscyloskop"
    )
    await Tag.create(
        epc="0000000deadbeef",
        RSSI=-20,
        last_active_at=datetime.now(timezone.utc),
        status=TagStatus.ACTIVE,
        name="Radziecki przyrząd"
    )


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    run_async(main())
