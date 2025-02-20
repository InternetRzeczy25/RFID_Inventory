from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from tortoise.contrib.pydantic import pydantic_model_creator

from server.api._base import add_get_all, add_get_one, add_patch, add_post
from server.models import Location

router = APIRouter(prefix="/locations", tags=["Locations"])

pydantic_Location = pydantic_model_creator(
    Location, name="Location", exclude=("tags.events",)
)
pydantic_batch_Location = pydantic_model_creator(
    Location,
    name="Location_batch",
    include=("device_id", "name", "id"),
)


class pydantic_Update_Location(BaseModel):
    name: str
    model_config = ConfigDict(title="UpdateLocation")


add_get_all(router, pydantic_batch_Location, Location.all)
add_get_one(router, pydantic_Location, int, Location.get)
add_patch(router, pydantic_batch_Location, pydantic_Update_Location, Location)
