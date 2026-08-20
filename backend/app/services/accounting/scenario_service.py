from datetime import datetime, timezone

from app.models.accounting.account import Account
from app.models.accounting.analytical import AnalyticalDimensionValue
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.scenario import Scenario, ScenarioAssumption
from app.schemas.accounting.scenario import ScenarioAssumptionCreate, ScenarioCreate
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class ScenarioService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def create(self, organization_id: str, actor_user_id: str, data: ScenarioCreate) -> Scenario:
        scenario = Scenario(organization_id=organization_id, fiscal_year_id=data.fiscal_year_id, code=data.code, name=data.name, description=data.description, status="DRAFT")
        self.session.add(scenario)
        try:
            await self.session.flush()
            await self.audit.record(organization_id, actor_user_id, "FPA_SCENARIO_CREATED", "Scenario", scenario.id, new_value={"code": scenario.code, "fiscal_year_id": scenario.fiscal_year_id})
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Scenario code already exists for this organization and fiscal year")
        return scenario

    async def add_assumption(self, organization_id: str, actor_user_id: str, scenario_id: str, data: ScenarioAssumptionCreate) -> ScenarioAssumption:
        scenario = await self._get(organization_id, scenario_id, for_update=True)
        if scenario.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only DRAFT scenarios can be changed")
        period = await self.session.scalar(select(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id, FiscalPeriod.id == data.fiscal_period_id, FiscalPeriod.fiscal_year_id == scenario.fiscal_year_id))
        if period is None:
            raise HTTPException(status_code=422, detail="Fiscal period does not belong to the scenario fiscal year")
        account = await self.session.scalar(select(Account).where(Account.organization_id == organization_id, Account.id == data.account_id))
        if account is None:
            raise HTTPException(status_code=422, detail="Account not found in organization")
        if data.dimension_value_id:
            dimension_value = await self.session.scalar(select(AnalyticalDimensionValue).where(AnalyticalDimensionValue.organization_id == organization_id, AnalyticalDimensionValue.id == data.dimension_value_id, AnalyticalDimensionValue.is_active == "true"))
            if dimension_value is None:
                raise HTTPException(status_code=422, detail="Analytical dimension value not found in organization")
        assumption = ScenarioAssumption(organization_id=organization_id, scenario_id=scenario.id, fiscal_period_id=period.id, account_id=account.id, dimension_value_id=data.dimension_value_id, amount=data.amount, rationale=data.rationale, created_by_user_id=actor_user_id)
        self.session.add(assumption)
        try:
            await self.session.flush()
            await self.audit.record(organization_id, actor_user_id, "FPA_SCENARIO_ASSUMPTION_ADDED", "ScenarioAssumption", assumption.id, new_value={"scenario_id": scenario.id, "period_id": period.id, "account_id": account.id, "amount": str(data.amount), "rationale": data.rationale})
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="An assumption already exists for this scenario scope")
        return assumption

    async def approve(self, organization_id: str, actor_user_id: str, scenario_id: str) -> Scenario:
        scenario = await self._get(organization_id, scenario_id, for_update=True)
        if scenario.status == "APPROVED":
            return scenario
        if scenario.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Locked scenario cannot be approved")
        count = await self.session.scalar(select(func.count(ScenarioAssumption.id)).where(ScenarioAssumption.organization_id == organization_id, ScenarioAssumption.scenario_id == scenario.id))
        if not count:
            raise HTTPException(status_code=422, detail="A scenario requires at least one explicit assumption")
        scenario.status = "APPROVED"
        scenario.approved_at = datetime.now(timezone.utc)
        scenario.approved_by_user_id = actor_user_id
        await self.audit.record(organization_id, actor_user_id, "FPA_SCENARIO_APPROVED", "Scenario", scenario.id, new_value={"status": scenario.status, "assumption_count": count})
        await self.session.commit()
        return scenario

    async def status(self, organization_id: str, scenario_id: str) -> dict:
        scenario = await self._get(organization_id, scenario_id)
        count = await self.session.scalar(select(func.count(ScenarioAssumption.id)).where(ScenarioAssumption.organization_id == organization_id, ScenarioAssumption.scenario_id == scenario.id))
        return {"scenario_id": scenario.id, "status": scenario.status, "assumption_count": int(count or 0), "ready": scenario.status in {"APPROVED", "LOCKED"} and bool(count)}

    async def _get(self, organization_id: str, scenario_id: str, for_update: bool = False) -> Scenario:
        query = select(Scenario).where(Scenario.organization_id == organization_id, Scenario.id == scenario_id)
        if for_update:
            query = query.with_for_update()
        scenario = await self.session.scalar(query)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return scenario
