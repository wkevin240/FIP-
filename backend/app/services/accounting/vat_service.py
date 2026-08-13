from datetime import date
from decimal import Decimal

from app.domain.accounting.vat.rules import VATRules
from app.models.accounting.account import Account
from app.models.accounting.vat import VATEntry, VATRate
from app.repositories.accounting.vat_repository import VATRepository
from app.schemas.accounting.vat import (
    VATCalculationRequest,
    VATCalculationResponse,
    VATEntryCreate,
    VATRateCreate,
    VATRateUpdate,
    VATSummaryResponse,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class VATService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = VATRepository(session)

    async def create_rate(self, organization_id: str, data: VATRateCreate) -> VATRate:
        await self._validate_tax_accounts(
            organization_id, data.input_vat_account_id, data.output_vat_account_id
        )
        try:
            rate = await self.repository.create_rate(organization_id, data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="VAT rate code already exists for this effective date",
            ) from exc
        await self.session.refresh(rate)
        return rate

    async def list_rates(self, organization_id: str) -> list[VATRate]:
        return await self.repository.list_rates(organization_id)

    async def update_rate(
        self, organization_id: str, rate_id: str, data: VATRateUpdate
    ) -> VATRate:
        rate = await self.repository.get_rate(organization_id, rate_id)
        if rate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="VAT rate not found"
            )
        changes = data.model_dump(exclude_unset=True)
        effective_to = changes.get("effective_to", rate.effective_to)
        if effective_to is not None and effective_to < rate.effective_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Effective end date must not precede effective start date",
            )
        input_account_id = changes.get(
            "input_vat_account_id", rate.input_vat_account_id
        )
        output_account_id = changes.get(
            "output_vat_account_id", rate.output_vat_account_id
        )
        await self._validate_tax_accounts(
            organization_id, input_account_id, output_account_id
        )
        for field, value in changes.items():
            setattr(rate, field, value)
        await self.session.commit()
        await self.session.refresh(rate)
        return rate

    async def calculate(
        self, organization_id: str, data: VATCalculationRequest
    ) -> VATCalculationResponse:
        rate = await self._get_effective_rate(
            organization_id, data.vat_rate_id, data.tax_date
        )
        vat_amount = VATRules.calculate_vat(
            Decimal(data.taxable_amount), Decimal(rate.rate)
        )
        return VATCalculationResponse(
            **data.model_dump(),
            vat_amount=vat_amount,
            total_amount=Decimal(data.taxable_amount) + vat_amount,
        )

    async def create_entry(
        self, organization_id: str, data: VATEntryCreate
    ) -> VATEntry:
        rate = await self._get_effective_rate(
            organization_id, data.vat_rate_id, data.tax_date
        )
        journal_entry = await self.repository.get_posted_journal_entry(
            organization_id, data.journal_entry_id
        )
        if journal_entry is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Posted journal entry not found",
            )
        if journal_entry.entry_date != data.tax_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="VAT date must equal the journal entry date",
            )
        if await self.repository.get_entry_by_journal_entry(
            organization_id, data.journal_entry_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Journal entry already has a VAT entry",
            )
        required_account_id = (
            rate.input_vat_account_id
            if data.direction == "INPUT"
            else rate.output_vat_account_id
        )
        if required_account_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="VAT rate is missing the required tax account for this direction",
            )

        vat_amount = VATRules.calculate_vat(
            Decimal(data.taxable_amount), Decimal(rate.rate)
        )
        try:
            vat_entry = VATEntry(
                organization_id=organization_id,
                vat_rate_id=rate.id,
                journal_entry_id=journal_entry.id,
                direction=data.direction,
                tax_date=data.tax_date,
                taxable_amount=data.taxable_amount,
                vat_amount=vat_amount,
            )
            await self.repository.create_entry(vat_entry)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Journal entry already has a VAT entry",
            ) from exc
        await self.session.refresh(vat_entry)
        return vat_entry

    async def summary(
        self, organization_id: str, start_date: date, end_date: date
    ) -> VATSummaryResponse:
        try:
            VATRules.validate_period(start_date, end_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        totals = await self.repository.summary(organization_id, start_date, end_date)
        return VATSummaryResponse(
            start_date=start_date,
            end_date=end_date,
            total_output_vat=totals["OUTPUT"],
            total_input_vat=totals["INPUT"],
            net_vat_payable=totals["OUTPUT"] - totals["INPUT"],
        )

    async def _get_effective_rate(
        self, organization_id: str, rate_id: str, tax_date: date
    ) -> VATRate:
        rate = await self.repository.get_effective_rate(
            organization_id, rate_id, tax_date
        )
        if rate is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active VAT rate not found for tax date",
            )
        return rate

    async def _validate_tax_accounts(
        self,
        organization_id: str,
        input_vat_account_id: str | None,
        output_vat_account_id: str | None,
    ) -> None:
        await self._validate_account_type(
            organization_id, input_vat_account_id, "ASSET", "input VAT"
        )
        await self._validate_account_type(
            organization_id, output_vat_account_id, "LIABILITY", "output VAT"
        )

    async def _validate_account_type(
        self,
        organization_id: str,
        account_id: str | None,
        expected_type: str,
        label: str,
    ) -> None:
        if account_id is None:
            return
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == account_id,
                Account.is_active.is_(True),
            )
        )
        if account is None or account.account_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Active {expected_type.lower()} account required for {label}",
            )
