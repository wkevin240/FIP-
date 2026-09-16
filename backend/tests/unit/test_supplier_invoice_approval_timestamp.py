from sqlalchemy import DateTime

from app.models.supplier_invoice import SupplierInvoice


def test_supplier_invoice_approved_at_is_timezone_aware() -> None:
    column = SupplierInvoice.__table__.c.approved_at

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
