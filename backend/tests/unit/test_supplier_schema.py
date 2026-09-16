import pytest
from pydantic import ValidationError

from app.schemas.supplier import SupplierCreate, SupplierUpdate


def test_supplier_create_normalizes_code_and_legal_name() -> None:
    supplier = SupplierCreate(code="  sup-001  ", legal_name="  Fournisseur SA  ")

    assert supplier.code == "SUP-001"
    assert supplier.legal_name == "Fournisseur SA"


def test_supplier_create_rejects_blank_code_and_legal_name() -> None:
    with pytest.raises(ValidationError):
        SupplierCreate(code="   ", legal_name="Fournisseur SA")

    with pytest.raises(ValidationError):
        SupplierCreate(code="SUP-001", legal_name="   ")


def test_supplier_update_rejects_blank_legal_name() -> None:
    with pytest.raises(ValidationError):
        SupplierUpdate(legal_name="   ")


def test_supplier_update_allows_clearing_optional_fields() -> None:
    supplier = SupplierUpdate(trade_name="   ", tax_id="   ")

    assert supplier.trade_name is None
    assert supplier.tax_id is None
