"""Ninja pagination returning ``{"results": [...], "count": n}``.

The ``results``/``count`` shape (rather than Ninja's default ``items``) keeps
the React frontend contract identical to the previous DRF implementation.
"""
from typing import Any

from ninja import Field, Schema
from ninja.pagination import PaginationBase

MAX_PAGE_SIZE = 1000


class DefaultPagination(PaginationBase):
    items_attribute = "results"

    class Input(Schema):
        page: int = Field(1, ge=1)
        page_size: int = Field(25, ge=1, le=MAX_PAGE_SIZE)

    class Output(Schema):
        results: list[Any]
        count: int

    def paginate_queryset(self, queryset, pagination: "DefaultPagination.Input", **params):
        page = pagination.page
        size = min(pagination.page_size, MAX_PAGE_SIZE)
        start = (page - 1) * size
        count = queryset.count() if hasattr(queryset, "count") else len(queryset)
        return {"results": list(queryset[start : start + size]), "count": count}
