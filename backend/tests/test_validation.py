import pytest
from fastapi import HTTPException

from app.core.validation import validate_pagination


def test_validate_pagination_accepts_normal_values() -> None:
    assert validate_pagination(0, 100) == (0, 100)


@pytest.mark.parametrize("skip,limit", [(-1, 10), (0, 0), (0, 501)])
def test_validate_pagination_rejects_invalid_values(skip: int, limit: int) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_pagination(skip, limit)
    assert exc_info.value.status_code == 422
