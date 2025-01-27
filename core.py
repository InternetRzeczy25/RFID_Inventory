import asyncio
import logging
import os
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass
from datetime import datetime as dt
from datetime import timezone as tz
from datetime import timedelta as td

from functools import partial
from parser import ReadEvent
from typing import Any

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    Model,
    SqliteDatabase,
)

logr = logging.getLogger("RFID Gateway")
logging.basicConfig(level=logging.DEBUG)

now = partial(dt.now, tz.utc)
TIMEOUT = td(seconds=float(os.environ.get("KEON_MQTT_DATA_TIMEOUT", 10.0)))

db = SqliteDatabase("tags.db")
db.connect()


@dataclass
class CEntry:
    t: float
    evt: ReadEvent


class BaseModel(Model):
    class Meta:
        database = db

    def update_instance(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.save()


class TagRFID(BaseModel):
    _id = AutoField()
    tag_id = CharField(index=True)
    active = BooleanField(default=False)
    location = CharField(default="unknown")
    lseen = DateTimeField()


TagRFID.create_table(safe=True)

"""
List of callbacks that will be run on the following events in the following order:

Order:
1. CHANGE LOCATION
2. CHANGE PRESENCE
"""
CallbackSequence = Sequence[Callable[[Any], Coroutine]]


async def processEvent(evt: ReadEvent, onEvents: CallbackSequence):
    tag, _ = TagRFID.get_or_create(tag_id=evt.tag_id, defaults={"lseen": dt.now()})

    if tag.location != evt.location:
        logr.info(f"Tag CHANGE LOCATION for {evt}")
        tag.location = evt.location
        await onEvents[0](evt)

    if not tag.active:
        logr.info(f"Tag APPEARED for {evt}")
        tag.active = True
        await onEvents[1](evt, True)

    tag.update_instance(lseen=dt.now())
    logr.info(f"Tag PRESENT for {evt}")
    await asyncio.sleep(TIMEOUT.seconds + TIMEOUT.microseconds / 1e6)
    if (dt.now() - TagRFID.get_by_id(tag._id).lseen) > (TIMEOUT - td(seconds=0.01)):
        logr.info(f"Tag LOST for {evt}")
        tag.update_instance(active=False)
        await onEvents[1](evt, False)
