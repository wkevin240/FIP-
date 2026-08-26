import hashlib
import json
from datetime import datetime, timezone

from app.models.accounting.closing_signoff import ClosingSignoff
from app.schemas.accounting.closing_signoff import ClosingSignoffResponse
from app.services.accounting.financial_closing_control_service import (
    FinancialClosingControlService,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class ClosingSignoffService:
    """Creates an auditable sign-off only for a fully ready financial year."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.control = FinancialClosingControlService(session)
        self.audit = AuditService(session)

    async def get(
        self, organization_id: str, fiscal_year_id: str
    ) -> ClosingSignoffResponse:
        signoff = await self.session.scalar(
            select(ClosingSignoff).where(
                ClosingSignoff.organization_id == organization_id,
                ClosingSignoff.fiscal_year_id == fiscal_year_id,
            )
        )
        if signoff is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Closing sign-off not found for organization and fiscal year",
            )
        return ClosingSignoffResponse.model_validate(signoff)

    async def sign(
        self,
        organization_id: str,
        fiscal_year_id: str,
        fiscal_period_id: str,
        actor_user_id: str,
    ) -> ClosingSignoffResponse:
        existing = await self.session.scalar(
            select(ClosingSignoff).where(
                ClosingSignoff.organization_id == organization_id,
                ClosingSignoff.fiscal_year_id == fiscal_year_id,
            )
        )
        if existing is not None:
            if existing.status == "SIGNED":
                return ClosingSignoffResponse.model_validate(existing)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Closing sign-off is revoked and requires an explicit workflow",
            )

        control = await self.control.assess(
            organization_id, fiscal_year_id, fiscal_period_id
        )
        if control.status != "READY":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CLOSING_NOT_READY",
                    "status": control.status,
                    "blockers": [
                        blocker.model_dump(mode="json") for blocker in control.blockers
                    ],
                },
            )

        snapshot = json.dumps(
            control.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        control_hash = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        signoff = ClosingSignoff(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year_id,
            status="SIGNED",
            signed_by_user_id=actor_user_id,
            signed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            control_hash=control_hash,
            control_snapshot=snapshot,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(signoff)
                await self.session.flush()
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Closing sign-off already exists for this organization and fiscal year",
            ) from exc

        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="CLOSING_SIGNOFF_CREATED",
            resource_type="ClosingSignoff",
            resource_id=signoff.id,
            new_value={
                "fiscal_year_id": fiscal_year_id,
                "fiscal_period_id": fiscal_period_id,
                "control_hash": control_hash,
                "status": "SIGNED",
            },
            context={"control_hash": control_hash},
        )
        return ClosingSignoffResponse.model_validate(signoff)
