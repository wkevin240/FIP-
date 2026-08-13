import json
from decimal import Decimal

from app.domain.payroll.calculation.rules import (
    PayrollCalculationRules,
    TaxBracketInput,
)
from app.models.accounting.account import Account
from app.models.accounting.journal import Journal
from app.models.payroll.payroll_period import PayrollAccountingProfile, PayrollRuleSet
from app.repositories.payroll.audit_repository import PayrollAuditRepository
from app.repositories.payroll.configuration_repository import (
    PayrollAccountingProfileRepository,
    PayrollRuleSetRepository,
)
from app.schemas.payroll.configuration import (
    PayrollAccountingProfileCreate,
    PayrollRuleSetCreate,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class PayrollConfigurationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rule_sets = PayrollRuleSetRepository(session)
        self.accounting_profiles = PayrollAccountingProfileRepository(session)
        self.audit = PayrollAuditRepository(session)

    async def get_rule_set(
        self, organization_id: str, rule_set_id: str
    ) -> PayrollRuleSet:
        rule_set = await self.rule_sets.get_by_id(organization_id, rule_set_id)
        if rule_set is None:
            raise HTTPException(status_code=404, detail="Payroll rule set not found")
        return rule_set

    async def create_rule_set(
        self, organization_id: str, actor_user_id: str, data: PayrollRuleSetCreate
    ) -> PayrollRuleSet:
        try:
            self._validate_tax_brackets(data)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        try:
            rule_set = await self.rule_sets.create(organization_id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "RULE_SET_CREATED",
                "PayrollRuleSet",
                rule_set.id,
                new_value=json.dumps(
                    {
                        "code": rule_set.code,
                        "effective_from": str(rule_set.effective_from),
                        "effective_to": str(rule_set.effective_to),
                    }
                ),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payroll rule set code already exists for this effective date",
            ) from exc
        return await self.get_rule_set(organization_id, rule_set.id)

    async def get_accounting_profile(
        self, organization_id: str, profile_id: str
    ) -> PayrollAccountingProfile:
        profile = await self.accounting_profiles.get_by_id(organization_id, profile_id)
        if profile is None:
            raise HTTPException(
                status_code=404, detail="Payroll accounting profile not found"
            )
        return profile

    async def create_accounting_profile(
        self,
        organization_id: str,
        actor_user_id: str,
        data: PayrollAccountingProfileCreate,
    ) -> PayrollAccountingProfile:
        if await self.accounting_profiles.get_by_code(
            organization_id, data.profile_code
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payroll accounting profile code already exists",
            )
        await self._validate_accounting_references(organization_id, data)
        try:
            profile = await self.accounting_profiles.create(organization_id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "ACCOUNTING_PROFILE_CREATED",
                "PayrollAccountingProfile",
                profile.id,
                new_value=json.dumps({"profile_code": profile.profile_code}),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payroll accounting profile code already exists",
            ) from exc
        await self.session.refresh(profile)
        return profile

    @staticmethod
    def _validate_tax_brackets(data: PayrollRuleSetCreate) -> None:
        if not data.tax_brackets:
            return
        brackets = [
            TaxBracketInput(
                lower_bound=bracket.lower_bound,
                upper_bound=bracket.upper_bound,
                rate=bracket.rate,
                sort_order=bracket.sort_order,
            )
            for bracket in data.tax_brackets
        ]
        PayrollCalculationRules._progressive_tax(Decimal("0.00"), brackets)

    async def _validate_accounting_references(
        self, organization_id: str, data: PayrollAccountingProfileCreate
    ) -> None:
        journal = await self.session.scalar(
            select(Journal).where(
                Journal.organization_id == organization_id,
                Journal.id == data.journal_id,
                Journal.is_active.is_(True),
            )
        )
        if journal is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active payroll journal is required",
            )
        account_ids = {
            data.salary_expense_account_id,
            data.employer_charge_account_id,
            data.employee_payable_account_id,
            data.tax_payable_account_id,
            data.social_payable_account_id,
            data.other_deduction_payable_account_id,
        }
        active_accounts = await self.session.scalars(
            select(Account.id).where(
                Account.organization_id == organization_id,
                Account.id.in_(account_ids),
                Account.is_active.is_(True),
            )
        )
        if len(set(active_accounts)) != len(account_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="All payroll accounting profile accounts must be active",
            )
