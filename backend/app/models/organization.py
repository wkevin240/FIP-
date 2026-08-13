from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    name = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    memberships = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    accounts = relationship("Account", back_populates="organization")
    fiscal_years = relationship("FiscalYear", back_populates="organization")
    fiscal_periods = relationship("FiscalPeriod", back_populates="organization")
    journals = relationship("Journal", back_populates="organization")
    journal_entries = relationship("JournalEntry", back_populates="organization")
    period_closings = relationship("PeriodClosing", back_populates="organization")
    bank_transactions = relationship("BankTransaction", back_populates="organization")
    bank_reconciliations = relationship(
        "BankReconciliation", back_populates="organization"
    )
    vat_rates = relationship("VATRate", back_populates="organization")
    vat_entries = relationship("VATEntry", back_populates="organization")
    products = relationship("Product", back_populates="organization")
    warehouses = relationship("Warehouse", back_populates="organization")
    stock_balances = relationship("StockBalance", back_populates="organization")
    stock_movements = relationship("StockMovement", back_populates="organization")
    invoices = relationship("Invoice", back_populates="organization")
    credit_notes = relationship("CreditNote", back_populates="organization")
    payments = relationship("Payment", back_populates="organization")
    treasury_bank_accounts = relationship(
        "TreasuryBankAccount", back_populates="organization"
    )
    payroll_employees = relationship("Employee", back_populates="organization")
    payroll_contracts = relationship(
        "EmploymentContract", back_populates="organization"
    )
    payroll_rule_sets = relationship("PayrollRuleSet", back_populates="organization")
    payroll_accounting_profiles = relationship(
        "PayrollAccountingProfile", back_populates="organization"
    )
    payroll_periods = relationship("PayrollPeriod", back_populates="organization")
    fixed_asset_accounting_profiles = relationship(
        "FixedAssetAccountingProfile", back_populates="organization"
    )
    fixed_asset_categories = relationship(
        "FixedAssetCategory", back_populates="organization"
    )
    fixed_assets = relationship("FixedAsset", back_populates="organization")
