import pytest
from pydantic import ValidationError

from app.schemas.customer import CustomerCreate, CustomerUpdate


def test_customer_create_normalizes_code_and_legal_name() -> None:
    customer = CustomerCreate(code="  c-001  ", legal_name="  Acme SA  ")

    assert customer.code == "C-001"
    assert customer.legal_name == "Acme SA"


def test_customer_create_rejects_blank_code_and_legal_name() -> None:
    with pytest.raises(ValidationError):
        CustomerCreate(code="   ", legal_name="Acme SA")

    with pytest.raises(ValidationError):
        CustomerCreate(code="C-001", legal_name="   ")


def test_customer_update_rejects_blank_legal_name() -> None:
    with pytest.raises(ValidationError):
        CustomerUpdate(legal_name="   ")


def test_customer_update_allows_explicitly_clearing_optional_fields() -> None:
    customer = CustomerUpdate(trade_name="   ", tax_id="   ")

    assert customer.trade_name is None
    assert customer.tax_id is None
