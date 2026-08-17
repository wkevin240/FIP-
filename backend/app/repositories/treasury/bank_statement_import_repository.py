from app.models.accounting.bank_transaction import BankTransaction
from app.models.treasury.bank_statement_import import BankStatementImport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class BankStatementImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_transactions_by_external_ids(
        self, organization_id: str, bank_account_id: str, external_ids: set[str]
    ) -> dict[str, BankTransaction]:
        result = await self.session.scalars(
            select(BankTransaction).where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.bank_account_id == bank_account_id,
                BankTransaction.external_id.in_(sorted(external_ids)),
            )
        )
        return {transaction.external_id: transaction for transaction in result}

    async def get_import_by_key(
        self, organization_id: str, idempotency_key: str
    ) -> BankStatementImport | None:
        return await self.session.scalar(
            select(BankStatementImport)
            .options(selectinload(BankStatementImport.lines))
            .where(
                BankStatementImport.organization_id == organization_id,
                BankStatementImport.idempotency_key == idempotency_key,
            )
        )

    async def get_import(
        self, organization_id: str, statement_import_id: str
    ) -> BankStatementImport | None:
        return await self.session.scalar(
            select(BankStatementImport)
            .options(selectinload(BankStatementImport.lines))
            .where(
                BankStatementImport.organization_id == organization_id,
                BankStatementImport.id == statement_import_id,
            )
        )

    async def create_import(self, statement_import: BankStatementImport) -> None:
        self.session.add(statement_import)
        await self.session.flush()

    async def create_transaction(self, transaction: BankTransaction) -> None:
        self.session.add(transaction)
        await self.session.flush()

    async def create_lines(self, lines: list) -> None:
        self.session.add_all(lines)
        await self.session.flush()

    async def lock_resources(self, resources: set[str]) -> None:
        if self.session.bind.dialect.name != "postgresql":
            return
        for resource in sorted(resources):
            await self.session.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtext('fip-bank-statement-import'), hashtext(:resource))"
                ),
                {"resource": resource},
            )
