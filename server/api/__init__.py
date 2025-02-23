from tortoise import Tortoise

Tortoise.init_models(["server.models"], "models")

from fastapi import APIRouter

from server.api import device, location, tag
from server.api.discover import discover_devices
from server.api.v1 import add_devices, add_locations, add_tags

api_v2 = APIRouter(tags=["API_V2"])

api_v2.include_router(device.router)
api_v2.include_router(tag.router)
api_v2.include_router(location.router)

api_v2.add_api_route("/discover", discover_devices, tags=["Utilities"])

api_v1 = APIRouter(tags=["API_V1"])

add_tags(api_v1)
add_devices(api_v1)
add_locations(api_v1)
