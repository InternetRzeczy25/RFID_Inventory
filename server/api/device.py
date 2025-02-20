from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from tortoise.contrib.pydantic import pydantic_model_creator

from server.models import Device

router = APIRouter(prefix="/devices", tags=["Devices"])


pydantic_Device = pydantic_model_creator(
    Device, name="Device", exclude=("locations.tags",)
)
pydantic_batch_Device = pydantic_model_creator(
    Device,
    name="Device_batch",
    exclude=("meta", "locations"),
)
pydantic_Create_Device = pydantic_model_creator(
    Device,
    exclude_readonly=True,
    exclude=("last_active_at", "online"),
    name="CreateDevice",
)


class pydantic_Update_Device(BaseModel):
    name: str | None = None
    ip: str | None = None
    model_config = ConfigDict(title="UpdateDevice")


@router.get("")
async def get_devices() -> list[pydantic_batch_Device]:  # type: ignore
    return await pydantic_batch_Device.from_queryset(Device.all())


@router.get("/{item_id}")
async def get_device(item_id: int) -> pydantic_Device:  # type: ignore
    return await pydantic_Device.from_queryset_single(Device.get(id=item_id))


@router.post("")
async def create_device(device: pydantic_Create_Device) -> pydantic_Device:  # type: ignore
    return await pydantic_Device.from_tortoise_orm(await Device.create(**device.dict()))


@router.patch("/{item_id}")
async def update_device(
    item_id: int,
    device: pydantic_Update_Device,  # type: ignore
) -> pydantic_Device:  # type: ignore
    await Device.filter(id=item_id).update(**device.model_dump(exclude_unset=True))
    return await pydantic_Device.from_queryset_single(Device.get(id=item_id))
