from datetime import date

from app.models.payroll.payroll_period import (
    PayrollAccountingProfile,
    PayrollContributionRule,
    PayrollRuleSet,
    PayrollTaxBracket,
)
from app.schemas.payroll.configuration import (
    PayrollAccountingProfileCreate,
    PayrollRuleSetCreate,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class PayrollRuleSetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _options(self, statement):
        return statement.options(
            selectinload(PayrollRuleSet.contribution_rules),
            selectinload(PayrollRuleSet.tax_brackets),
        )

    async def get_by_id(
        self, organization_id: str, rule_set_id: str
    ) -> PayrollRuleSet | None:
        return await self.session.scalar(
            self._options(
                select(PayrollRuleSet).where(
                    PayrollRuleSet.organization_id == organization_id,
                    PayrollRuleSet.id == rule_set_id,
                )
            )
        )

    async def get_effective(
        self, organization_id: str, effective_date: date
    ) -> PayrollRuleSet | None:
        return await self.session.scalar(
            self._options(
                select(PayrollRuleSet)
                .where(
                    PayrollRuleSet.organization_id == organization_id,
                    PayrollRuleSet.is_active.is_(True),
                    PayrollRuleSet.effective_from <= effective_date,
                    (PayrollRuleSet.effective_to.is_(None))
                    | (PayrollRuleSet.effective_to >= effective_date),
                )
                .order_by(PayrollRuleSet.effective_from.desc())
            )
        )

    async def create(
        self, organization_id: str, data: PayrollRuleSetCreate
    ) -> PayrollRuleSet:
        rule_set = PayrollRuleSet(
            organization_id=organization_id,
            contribution_rules=[
                PayrollContributionRule(**rule.model_dump())
                for rule in data.contribution_rules
            ],
            tax_brackets=[
                PayrollTaxBracket(**bracket.model_dump())
                for bracket in data.tax_brackets
            ],
            **data.model_dump(exclude={"contribution_rules", "tax_brackets"}),
        )
        self.session.add(rule_set)
        await self.session.flush()
        return rule_set


class PayrollAccountingProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, profile_id: str
    ) -> PayrollAccountingProfile | None:
        return await self.session.scalar(
            select(PayrollAccountingProfile).where(
                PayrollAccountingProfile.organization_id == organization_id,
                PayrollAccountingProfile.id == profile_id,
            )
        )

    async def get_by_code(
        self, organization_id: str, profile_code: str
    ) -> PayrollAccountingProfile | None:
        return await self.session.scalar(
            select(PayrollAccountingProfile).where(
                PayrollAccountingProfile.organization_id == organization_id,
                PayrollAccountingProfile.profile_code == profile_code,
            )
        )

    async def create(
        self, organization_id: str, data: PayrollAccountingProfileCreate
    ) -> PayrollAccountingProfile:
        profile = PayrollAccountingProfile(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(profile)
        await self.session.flush()
        return profile
