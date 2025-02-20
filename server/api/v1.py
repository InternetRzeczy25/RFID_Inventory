from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from tortoise.contrib.pydantic import pydantic_model_creator

from server.models import Device, Location, Tag, Event

pydantic_Device = pydantic_model_creator(
    Device, name="Device", exclude=("locations.tags",)
)
pydantic_batch_Device = pydantic_model_creator(
    Device,
    name="Device_batch",
    exclude=("meta", "locations.tags"),
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


def add_devices(router: APIRouter) -> None:
    tags = ["Devices"]

    @router.get("/devices", tags=tags)
    async def get_devices() -> list[pydantic_batch_Device]:  # type: ignore
        return await pydantic_batch_Device.from_queryset(Device.all())

    @router.get("/devices/{item_id}", tags=tags)
    async def get_device(item_id: int) -> pydantic_Device:  # type: ignore
        return await pydantic_Device.from_queryset_single(Device.get(id=item_id))

    @router.post("/devices", tags=tags)
    async def create_device(device: pydantic_Create_Device) -> pydantic_Device:  # type: ignore
        return await pydantic_Device.from_tortoise_orm(
            await Device.create(**device.dict())
        )

    @router.patch("/devices/{item_id}", tags=tags)
    async def update_device(
        item_id: int,
        device: pydantic_Update_Device,  # type: ignore
    ) -> pydantic_Device:  # type: ignore
        await Device.filter(id=item_id).update(**device.model_dump(exclude_unset=True))
        return await pydantic_Device.from_queryset_single(Device.get(id=item_id))


pydantic_Tag = pydantic_model_creator(Tag, name="Tag")
pydantic_batch_Tag = pydantic_model_creator(
    Tag,
    name="Tag_batch",
    exclude=("events", "last_loc_seen.device"),
)


class pydantic_Update_Tag(BaseModel):
    name: str | None = None
    description: str | None = None


def add_tags(router: APIRouter) -> None:
    tags = ["Tags"]

    @router.get("/tags", tags=tags)
    async def get_tags() -> list[pydantic_batch_Tag]:  # type: ignore
        return await pydantic_batch_Tag.from_queryset(
            Tag.all().prefetch_related("last_loc_seen")
        )

    @router.get("/tags/{item_id}", tags=tags)
    async def get_tag(item_id: int) -> pydantic_Tag:  # type: ignore
        return await pydantic_Tag.from_queryset_single(Tag.get(id=item_id))

    @router.patch("/tags/{item_id}", tags=tags)
    async def update_tag(item_id: int, tag: pydantic_Update_Tag) -> pydantic_Tag:  # type: ignore
        await Tag.filter(id=item_id).update(**tag.dict(exclude_unset=True))
        return await pydantic_Tag.from_queryset_single(Tag.get(id=item_id))


pydantic_Location = pydantic_model_creator(
    Location, name="Location", exclude=("tags.events",)
)
pydantic_batch_Location = pydantic_model_creator(
    Location,
    name="Location_batch",
    include=("device_id", "name", "loc", "id"),
)
pydantic_Create_Location = pydantic_model_creator(
    Location,
    include=("loc", "name", "device_id"),
    name="CreateLocation",
)


class pydantic_Update_Location(BaseModel):
    name: str
    model_config = ConfigDict(title="UpdateLocation")


def add_locations(router: APIRouter) -> None:
    tags = ["Locations"]

    @router.get("/locations", tags=tags)
    async def get_locations() -> list[pydantic_batch_Location]:  # type: ignore
        return await pydantic_batch_Location.from_queryset(Location.all())

    @router.get("/locations/{item_id}", tags=tags)
    async def get_location(item_id: str) -> pydantic_Location:  # type: ignore
        return await pydantic_Location.from_queryset_single(Location.get(id=item_id))

    @router.post("/locations", tags=tags)
    async def create_location(location: pydantic_Create_Location) -> pydantic_Location:  # type: ignore
        return await pydantic_Location.from_tortoise_orm(
            await Location.create(**location.model_dump())
        )

    @router.patch("/locations/{item_id}", tags=tags)
    async def update_location(
        item_id: str,
        location: pydantic_Update_Location,  # type: ignore
    ) -> pydantic_Location:  # type: ignore
        await Location.filter(id=item_id).update(
            **location.model_dump(exclude_unset=True)
        )
        return await pydantic_Location.from_queryset_single(Location.get(id=item_id))


pydantic_Event = pydantic_model_creator(Event, name="Event")
pydantic_In_Event = pydantic_model_creator(Event, exclude_readonly=True, name="InEvent")


def add_events(router: APIRouter) -> None:
    @router.get("/events")
    async def get_events() -> list[pydantic_Event]:  # type: ignore
        return await pydantic_Event.from_queryset(Event.all())

    @router.get("/events/{event_id}")
    async def get_event(event_id: int) -> pydantic_Event:  # type: ignore
        return await pydantic_Event.from_queryset_single(Event.get(id=event_id))
