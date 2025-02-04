from enum import IntEnum

from tortoise import fields
from tortoise.models import Model


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
    name = fields.CharField(max_length=255)
    device = fields.ForeignKeyField("models.Device", related_name="locations")


class TagStatus(IntEnum):
    ACTIVE = 0
    LOST = 1


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
        return self.name


class Event(Model):
    _id = fields.IntField(pk=True)
    tag = fields.ForeignKeyField("models.Tag", related_name="event")
    event = fields.IntField()
    notified = fields.BooleanField()
    data = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)
