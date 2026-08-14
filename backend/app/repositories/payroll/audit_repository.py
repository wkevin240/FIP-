import json

from app.models.payroll.payroll import PayrollAuditEvent
from app.repositories.audit.audit_event_repository import AuditEventRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class PayrollAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.transversal_audit = AuditEventRepository(session)

    async def append(
        self,
        organization_id: str,
        actor_user_id: str | None,
        action: str,
        object_type: str,
        object_id: str,
        payroll_period_id: str | None = None,
        previous_value: str | None = None,
        new_value: str | None = None,
        reason: str | None = None,
    ) -> PayrollAuditEvent:
        event = PayrollAuditEvent(
            organization_id=organization_id,
            payroll_period_id=payroll_period_id,
            actor_user_id=actor_user_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
        )
        self.session.add(event)
        await self.session.flush()
        await self.transversal_audit.append(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=object_type,
            resource_id=object_id,
            previous_value=json.loads(previous_value) if previous_value else None,
            new_value=json.loads(new_value) if new_value else None,
            context={"payroll_period_id": payroll_period_id, "reason": reason}
            if payroll_period_id or reason
            else None,
            transaction_id=payroll_period_id or object_id,
        )
        return event

    async def list_for_period(
        self, organization_id: str, payroll_period_id: str
    ) -> list[PayrollAuditEvent]:
        result = await self.session.scalars(
            select(PayrollAuditEvent)
            .where(
                PayrollAuditEvent.organization_id == organization_id,
                PayrollAuditEvent.payroll_period_id == payroll_period_id,
            )
            .order_by(PayrollAuditEvent.occurred_at, PayrollAuditEvent.id)
        )
        return list(result)
