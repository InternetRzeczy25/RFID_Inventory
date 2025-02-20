from typing import Callable, Any, Type
from tortoise.queryset import QuerySet, QuerySetSingle
from tortoise.models import Model
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError


def add_get_one(router, out_type, in_type, query: Callable[[Any], QuerySetSingle]):
    @router.get("/{item_id}")
    async def get_one(item_id: in_type) -> out_type:  # type: ignore
        return await out_type.from_queryset_single(query(id=item_id))


def add_get_all(router, out_type, query: Callable[[], QuerySet]):
    @router.get("")
    async def get_all() -> list[out_type]:  # type: ignore
        return await out_type.from_queryset(query())


def forward_exception(e: Exception):
    print(e)
    raise RequestValidationError(
        errors=(
            ValidationError.from_exception_data(
                e.__class__.__name__,
                [
                    InitErrorDetails(
                        type=PydanticCustomError(e.__class__.__name__, str(e)),
                        loc=("się", "zjebało"),
                    )
                ],
            )
        ).errors()
    )


def add_post(router, out_type, in_type, model: Type[Model]):
    @router.post("")
    async def create(item: in_type) -> out_type:  # type: ignore
        try:
            return await out_type.from_tortoise_orm(
                await model.create(**item.model_dump())
            )
        except Exception as e:
            forward_exception(e)


def add_patch(router, out_type, in_type, model: Type[Model]):
    @router.patch("/{item_id}")
    async def update(item_id: int, item: in_type) -> out_type:  # type: ignore
        try:
            await model.filter(id=item_id).update(**item.model_dump(exclude_unset=True))
            return await out_type.from_queryset_single(model.get(id=item_id))
        except Exception as e:
            forward_exception(e)
