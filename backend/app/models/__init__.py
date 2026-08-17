"""Import mapped models so Alembic can discover their metadata."""

from app.models.accounting.account import Account
from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_transaction import BankTransaction
from app.models.accounting.cash_flow_account_mapping import CashFlowAccountMapping
from app.models.accounting.closing import PeriodClosing
from app.models.accounting.financial_statement_mapping import FinancialStatementMapping
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal import Journal
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.accounting.vat import VATEntry, VATRate
from app.models.accounting.vat_declaration import VATDeclaration
from app.models.audit import AuditEvent, AuditSequence
from app.models.fixed_assets import (
    DepreciationPlan,
    DepreciationScheduleLine,
    FixedAsset,
    FixedAssetAccountingProfile,
    FixedAssetAuditEvent,
    FixedAssetCategory,
    FixedAssetComponent,
    FixedAssetDisposal,
)
from app.models.inventory.accounting import (
    InventoryAccountingPosting,
    InventoryAccountingProfile,
)
from app.models.inventory.product import Product
from app.models.inventory.stock_balance import StockBalance
from app.models.inventory.stock_movement import StockMovement
from app.models.inventory.warehouse import Warehouse
from app.models.invoicing.accounting import (
    InvoiceAccountingPosting,
    InvoiceAccountingProfile,
)
from app.models.invoicing.credit_note import CreditNote
from app.models.invoicing.invoice import Invoice
from app.models.invoicing.invoice_line import InvoiceLine
from app.models.invoicing.payment import Payment
from app.models.membership import OrganizationMembership
from app.models.organization import Organization
from app.models.payroll import (
    Employee,
    EmploymentContract,
    PayrollAccountingProfile,
    PayrollAuditEvent,
    PayrollContributionRule,
    PayrollCorrection,
    PayrollInput,
    PayrollPeriod,
    PayrollRuleSet,
    PayrollSlip,
    PayrollSlipLine,
    PayrollTaxBracket,
)
from app.models.permission import Permission
from app.models.role import Role
from app.models.treasury.accounting import (
    TreasuryAccountingPosting,
    TreasuryAccountingProfile,
)
from app.models.treasury.bank_account import TreasuryBankAccount
from app.models.user import User

__all__ = [
    "Account",
    "AuditEvent",
    "AuditSequence",
    "BankReconciliation",
    "BankTransaction",
    "CashFlowAccountMapping",
    "CreditNote",
    "DepreciationPlan",
    "DepreciationScheduleLine",
    "Employee",
    "EmploymentContract",
    "FinancialStatementMapping",
    "FiscalPeriod",
    "FiscalYear",
    "FixedAsset",
    "FixedAssetAccountingProfile",
    "FixedAssetAuditEvent",
    "FixedAssetCategory",
    "FixedAssetComponent",
    "FixedAssetDisposal",
    "InventoryAccountingPosting",
    "InventoryAccountingProfile",
    "Invoice",
    "InvoiceAccountingPosting",
    "InvoiceAccountingProfile",
    "InvoiceLine",
    "Journal",
    "JournalEntry",
    "JournalEntryLine",
    "Organization",
    "OrganizationMembership",
    "Payment",
    "PayrollAccountingProfile",
    "PayrollAuditEvent",
    "PayrollContributionRule",
    "PayrollCorrection",
    "PayrollInput",
    "PayrollPeriod",
    "PayrollRuleSet",
    "PayrollSlip",
    "PayrollSlipLine",
    "PayrollTaxBracket",
    "PeriodClosing",
    "Permission",
    "Product",
    "Role",
    "StockBalance",
    "StockMovement",
    "TreasuryAccountingPosting",
    "TreasuryAccountingProfile",
    "TreasuryBankAccount",
    "User",
    "VATDeclaration",
    "VATEntry",
    "VATRate",
    "Warehouse",
]
