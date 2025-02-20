from tortoise.contrib.pydantic import pydantic_model_creator
from pydantic import BaseModel, ConfigDict, ValidationError
from server.models import Tag
from fastapi import APIRouter
from functools import partial
from ._base import add_get_all, add_get_one, add_post, add_patch

router = APIRouter(prefix="/tags", tags=["Tags"])


pydantic_Tag = pydantic_model_creator(Tag, name="Tag")
pydantic_batch_Tag = pydantic_model_creator(
    Tag,
    name="Tag_batch",
    exclude=("events", "last_loc_seen.device"),
)


class pydantic_Update_Tag(BaseModel):
    name: str | None = None
    description: str | None = None


def batch_tags_query():
    return Tag.all().prefetch_related("last_loc_seen")


add_get_all(router, pydantic_batch_Tag, batch_tags_query)
add_get_one(router, pydantic_Tag, int, Tag.get)
add_patch(router, pydantic_Tag, pydantic_Update_Tag, Tag)
