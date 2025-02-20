import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from pydantic import BaseModel
from tortoise import fields
from tortoise.models import Model
from tortoise.validators import RegexValidator


class TagStatus(IntEnum):
    ACTIVE = 0
    LOST = 1


class EventType(IntEnum):
    TAG_LOST = 0
    TAG_LOC_CHANGE = 1
    TAG_ADDED = 2
    TAG_REAPPEARED = 3


class TimestampMixin:
    created_at = fields.DatetimeField(auto_now_add=True)
    modified_at = fields.DatetimeField(auto_now=True)


class MQTT_Message(BaseModel):
    action: EventType
    tag_id: int
    loc_id: int
    past_loc_id: int
    event_id: int


class device_metadata(BaseModel):
    id: str
    family: str
    serial: str
    code: str
    fw_version: str
    rf_module: str


class Device(TimestampMixin, Model):
    id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField(auto_now_add=True)
    name = fields.CharField(max_length=255)
    mac = fields.CharField(max_length=255, index=True, unique=True)
    ip = fields.CharField(max_length=255)
    online = fields.BooleanField(index=True)
    meta = fields.JSONField(field_type=device_metadata)
    locations: fields.ReverseRelation["Location"]


class Location(TimestampMixin, Model):
    id = fields.IntField(pk=True)
    loc = fields.CharField(
        max_length=255,
        unique=True,
        validators=[
            RegexValidator(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}/[0-4]/[0-4]/[0-4]$", re.I)
        ],
    )  # MAC+... as key
    name = fields.CharField(max_length=255)
    device: fields.ForeignKeyRelation[Device] = fields.ForeignKeyField(
        "models.Device", related_name="locations"
    )
    tags: fields.ReverseRelation["Tag"]

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Tag(TimestampMixin, Model):
    id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField()
    epc = fields.CharField(max_length=255, index=True, unique=True)
    status: TagStatus = fields.IntEnumField(TagStatus, index=True)
    last_loc_seen: fields.ForeignKeyNullableRelation[Location] = fields.ForeignKeyField(
        "models.Location", related_name="tags", null=True, to_field="loc"
    )
    events: fields.ReverseRelation["Event"]
    name = fields.CharField(max_length=255)
    description = fields.TextField()
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
    notified = fields.BooleanField()
    data = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)
