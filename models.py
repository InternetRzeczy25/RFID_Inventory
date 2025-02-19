from dataclasses import dataclass
from enum import IntEnum
from typing import Any
from tortoise import fields
from tortoise.models import Model
from pydantic import BaseModel


class TagStatus(IntEnum):
    ACTIVE = 0
    LOST = 1


class EventType(IntEnum):
    TAG_LOST = 0
    TAG_LOC_CHANGE = 1
    TAG_ADDED = 2
    TAG_REAPPEARED = 3


class MQTT_Message(BaseModel):
    action: EventType
    tag_id: int
    loc_id: int
    past_loc_id: int
    event_id: int


class Device(Model):
    id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField(null=True, default=None)
    name = fields.CharField(max_length=255, default="-")
    mac = fields.CharField(max_length=255, index=True, unique=True)
    ip = fields.CharField(max_length=255)
    online = fields.BooleanField(index=True, default=False)
    meta = fields.JSONField()
    locations: fields.ReverseRelation["Location"]


class Location(Model):
    id = fields.CharField(pk=True, max_length=255)  # MAC+... as key
    name = fields.CharField(max_length=255, default="-")
    device: fields.ForeignKeyRelation[Device] = fields.ForeignKeyField(
        "models.Device", related_name="locations"
    )
    tags: fields.ReverseRelation["Tag"]

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Tag(Model):
    id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField()
    epc = fields.CharField(max_length=255, index=True, unique=True)
    status: TagStatus = fields.IntEnumField(TagStatus, index=True)
    last_loc_seen: fields.ForeignKeyNullableRelation[Location] = fields.ForeignKeyField(
        "models.Location", related_name="tags", null=True
    )
    events: fields.ReverseRelation["Event"]
    name = fields.CharField(max_length=255, default="-")
    description = fields.TextField(default="-")
    RSSI = fields.IntField()

    def __repr__(self):
        return f"name: {self.name}, EPC: {self.epc}"


@dataclass
class TagEvent:
    type: EventType
    tag: Tag
    data: dict[Any, Any] | list[Any]


class Event(Model):
    id = fields.IntField(pk=True)
    tag: fields.ForeignKeyRelation[Tag] = fields.ForeignKeyField(
        "models.Tag", related_name="events"
    )
    type: EventType = fields.IntEnumField(EventType, index=True)
    notified = fields.BooleanField(default=False)
    data = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)

