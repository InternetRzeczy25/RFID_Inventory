from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from tortoise.contrib.pydantic import pydantic_model_creator

from server.api._base import add_get_all, add_get_one, add_patch
from server.models import Device

router = APIRouter(prefix="/devices", tags=["Devices"])


pydantic_Device = pydantic_model_creator(
    Device, name="Device", exclude=("locations.tags",)
)
pydantic_batch_Device = pydantic_model_creator(
    Device,
    name="Device_batch",
    exclude=("meta", "locations", "created_at", "modified_at"),
)


class pydantic_Update_Device(BaseModel):
    name: str | None = None
    ip: str | None = None
    model_config = ConfigDict(title="UpdateDevice")


add_get_all(router, pydantic_batch_Device, Device.all)
add_get_one(router, pydantic_Device, int, Device.get)
add_patch(router, pydantic_Device, pydantic_Update_Device, Device)
