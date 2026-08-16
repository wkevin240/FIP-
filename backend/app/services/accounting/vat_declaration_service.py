import json
from datetime import datetime, timezone
from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.vat_declaration import VATDeclaration
from app.repositories.accounting.vat_declaration_repository import (
    VATDeclarationRepository,
)
from app.schemas.accounting.vat import VATDeclarationCreate
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class VATDeclarationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = VATDeclarationRepository(session)
        self.audit = AuditService(session)

    async def create(
        self,
        organization_id: str,
        actor_user_id: str,
        data: VATDeclarationCreate,
    ) -> VATDeclaration:
        period = await self.repository.get_period(
            organization_id, data.fiscal_period_id
        )
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Fiscal period not found"
            )
        if period.status != FiscalPeriodStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="VAT declarations require a closed fiscal period",
            )
        if await self.repository.get_by_period(organization_id, period.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A VAT declaration already exists for this fiscal period",
            )
        totals = await self.repository.totals(
            organization_id, period.start_date, period.end_date
        )
        output_vat = Decimal(totals["OUTPUT"])
        input_vat = Decimal(totals["INPUT"])
        declaration = VATDeclaration(
            organization_id=organization_id,
            fiscal_period_id=period.id,
            status="READY",
            total_output_vat=output_vat,
            total_input_vat=input_vat,
            net_vat_payable=output_vat - input_vat,
        )
        try:
            await self.repository.create(declaration)
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="VAT_DECLARATION_CREATED",
                resource_type="VATDeclaration",
                resource_id=declaration.id,
                new_value={
                    "fiscal_period_id": period.id,
                    "total_output_vat": str(output_vat),
                    "total_input_vat": str(input_vat),
                    "net_vat_payable": str(declaration.net_vat_payable),
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A VAT declaration already exists for this fiscal period",
            ) from exc
        await self.session.refresh(declaration)
        return declaration

    async def list(self, organization_id: str) -> list[VATDeclaration]:
        return await self.repository.list_declarations(organization_id)

    async def submit(
        self, organization_id: str, declaration_id: str, actor_user_id: str
    ) -> VATDeclaration:
        declaration = await self._get(organization_id, declaration_id)
        if declaration.status == "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="VAT declaration is already submitted",
            )
        declaration.status = "SUBMITTED"
        declaration.submitted_at = datetime.now(timezone.utc)
        declaration.submitted_by_user_id = actor_user_id
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="VAT_DECLARATION_SUBMITTED",
            resource_type="VATDeclaration",
            resource_id=declaration.id,
            previous_value={"status": "READY"},
            new_value={"status": "SUBMITTED"},
        )
        await self.session.commit()
        await self.session.refresh(declaration)
        return declaration

    async def export_json(
        self, organization_id: str, declaration_id: str, actor_user_id: str
    ) -> str:
        declaration = await self._get(organization_id, declaration_id)
        period = await self.repository.get_period(
            organization_id, declaration.fiscal_period_id
        )
        assert period is not None
        payload = {
            "framework": "SYSCOHADA",
            "declaration": {
                "id": declaration.id,
                "status": declaration.status,
                "total_output_vat": str(declaration.total_output_vat),
                "total_input_vat": str(declaration.total_input_vat),
                "net_vat_payable": str(declaration.net_vat_payable),
            },
            "period": {
                "id": period.id,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
            },
        }
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="VAT_DECLARATION_EXPORTED",
            resource_type="VATDeclaration",
            resource_id=declaration.id,
            context={"format": "json", "status": declaration.status},
        )
        await self.session.commit()
        return json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )

    async def _get(self, organization_id: str, declaration_id: str) -> VATDeclaration:
        declaration = await self.repository.get_declaration(
            organization_id, declaration_id
        )
        if declaration is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="VAT declaration not found",
            )
        return declaration
