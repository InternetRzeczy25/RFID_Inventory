import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import Any
from parser import ReadEvent

from peewee import AutoField, BooleanField, CharField, Model, SqliteDatabase

logr = logging.getLogger("RFID Gateway")
TIMEOUT = float(os.environ.get("KEON_MQTT_DATA_TIMEOUT", 10.0))
cache = {}

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


TagRFID.create_table(safe=True)

"""
List of callbacks that will be run on the following events in the following order:

Order:
1. CHANGE LOCATION
2. CHANGE PRESENCE
"""
CallbackSequence = Sequence[Callable[[Any], Coroutine]]


async def processEvent(evt: ReadEvent, onEvents: CallbackSequence):
    tag, _ = TagRFID.get_or_create(tag_id=evt.tag_id)

    if evt.tag_id in cache and cache[evt.tag_id].evt.location != evt.location:
        logr.info(f"Tag CHANGE LOCATION for {evt}")
        tag.update_instance(location=evt.location)
        await onEvents[0](evt)

    if not tag.active:
        logr.info(f"Tag APPEARED for {evt}")
        tag.update_instance(active=True)
        await onEvents[1](evt, True)
    cache[evt.tag_id] = CEntry(t=time.time(), evt=evt)

    logr.info(f"Tag PRESENT for {evt}")
    await asyncio.sleep(TIMEOUT)
    if (time.time() - cache[evt.tag_id].t) > (TIMEOUT - 0.01):
        logr.info(f"Tag LOST for {evt}")
        tag.update_instance(active=False)
        await onEvents[1](evt, False)