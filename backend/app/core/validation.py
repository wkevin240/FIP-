from __future__ import annotations

from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status


def validate_pagination(skip: int, limit: int, *, max_limit: int = 500) -> tuple[int, int]:
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="skip must be greater than or equal to 0",
        )
    if limit < 1 or limit > max_limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"limit must be between 1 and {max_limit}",
        )
    return skip, limit


def parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID",
        ) from exc


def ensure_no_duplicate(values: Iterable[str], field_name: str) -> None:
    items = list(values)
    if len(items) != len(set(items)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate values are not allowed for {field_name}",
        )
