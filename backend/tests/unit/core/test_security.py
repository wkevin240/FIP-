import pytest
from app.core.security import create_access_token, decode_access_token


def test_access_token_contains_required_claims() -> None:
    token = create_access_token("user-123", "org-456")

    payload = decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["org"] == "org-456"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_malformed_access_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token("not-a-valid-jwt")
