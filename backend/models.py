from dataclasses import dataclass
from enum import IntEnum
from typing import Any
from tortoise import fields
from tortoise.models import Model


class TagStatus(IntEnum):
    ACTIVE = 0
    LOST = 1


class TagEventType(IntEnum):
    TAG_LOST = 0
    TAG_LOC_CHANGE = 1
    TAG_ADDED = 2
    TAG_REAPPEARED = 3


class EventType(IntEnum):
    TAG_LOST = 0
    TAG_LOC_CHANGE = 1
    TAG_ADDED = 2
    TAG_REAPPEARED = 3


class Device(Model):
    _id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField()
    name = fields.CharField(max_length=255)
    mac = fields.CharField(max_length=255, index=True, unique=True)
    ip = fields.CharField(max_length=255)
    online = fields.BooleanField(index=True)
    meta = fields.JSONField()


class Location(Model):
    _id = fields.CharField(pk=True, max_length=255)  # MAC+... as key
    name = fields.CharField(max_length=255, default="-")
    device = fields.ForeignKeyField("models.Device", related_name="locations")

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Tag(Model):
    _id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField()
    epc = fields.CharField(max_length=255, index=True, unique=True)
    status: TagStatus = fields.IntEnumField(TagStatus, index=True)
    last_loc_seen = fields.ForeignKeyField(
        "models.Location", related_name="tag", null=True
    )
    name = fields.CharField(max_length=255, default="-")
    description = fields.TextField(default="-")
    RSSI = fields.IntField()

    def __repr__(self):
        return f"name: {self.name}, EPC: {self.epc}"


@dataclass
class TagEvent:
    type: TagEventType
    tag: Tag
    data: dict[Any, Any] | list[Any]


class Event(Model):
    _id = fields.IntField(pk=True)
    tag = fields.ForeignKeyField("models.Tag", related_name="event")
    type: EventType = fields.IntEnumField(EventType, index=True)
    notified = fields.BooleanField(default=False)
    data = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)
