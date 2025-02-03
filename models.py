from tortoise import fields
from tortoise.models import Model


class Devices(Model):
    _id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField()
    name = fields.CharField(max_length=255)
    mac = fields.CharField(max_length=255, index=True, unique=True)
    ip = fields.CharField(max_length=255)
    online = fields.BooleanField(index=True)
    meta = fields.JSONField()


class Locations(Model):
    _id = fields.CharField(pk=True, max_length=255)  # MAC+... as key
    name = fields.CharField(max_length=255)
    device = fields.ForeignKeyField("models.Devices", related_name="locations")


class Tags(Model):
    _id = fields.IntField(pk=True)
    last_active_at = fields.DatetimeField()
    epc = fields.CharField(max_length=255, index=True, unique=True)
    status = fields.IntField(index=True)
    last_loc_seen = fields.ForeignKeyField(
        "models.Locations", related_name="tags", null=True
    )
    name = fields.CharField(max_length=255)
    description = fields.TextField()
    RSSI = fields.IntField()


class Events(Model):
    _id = fields.IntField(pk=True)
    tag = fields.ForeignKeyField("models.Tags", related_name="events")
    event = fields.IntField()
    notified = fields.BooleanField()
    data = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)
