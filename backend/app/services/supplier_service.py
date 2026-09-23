from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.audit_context import AuditContext
from app.models.supplier import Supplier
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate


class SupplierService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierRepository(session)
        self.audit_repository = AuditLogRepository(session)

    @staticmethod
    def _audit_payload(supplier: Supplier) -> dict:
        return {
            "supplier_id": supplier.id,
            "code": supplier.code,
            "legal_name": supplier.legal_name,
            "trade_name": supplier.trade_name,
            "tax_id": supplier.tax_id,
            "email": supplier.email,
            "phone": supplier.phone,
            "address": supplier.address,
            "is_active": supplier.is_active,
        }

    async def get(self, organization_id: str, supplier_id: str) -> Supplier:
        supplier = await self.repository.get_by_id(organization_id, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        return supplier

    async def list(self, organization_id: str, skip: int = 0, limit: int = 100, is_active: bool | None = None) -> list[Supplier]:
        return await self.repository.list(organization_id, skip=skip, limit=limit, is_active=is_active)

    async def create(self, organization_id: str, actor_id: str, data: SupplierCreate) -> Supplier:
        if await self.repository.get_by_code(organization_id, data.code):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier code already exists")
        if data.tax_id and await self.repository.get_by_tax_id(organization_id, data.tax_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier tax ID already exists")
        supplier = Supplier(
            organization_id=organization_id,
            code=data.code,
            legal_name=data.legal_name,
            trade_name=data.trade_name,
            tax_id=data.tax_id,
            email=str(data.email) if data.email else None,
            phone=data.phone,
            address=data.address,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.repository.add(supplier)
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="SUPPLIER_CREATED"),
                entity_type="supplier", entity_id=supplier.id, payload=self._audit_payload(supplier),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier conflicts with existing master data") from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(supplier)
        return supplier

    async def update(self, organization_id: str, supplier_id: str, actor_id: str, data: SupplierUpdate) -> Supplier:
        supplier = await self.repository.get_for_update(organization_id, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return supplier
        if "tax_id" in changes and changes["tax_id"]:
            duplicate = await self.repository.get_by_tax_id(organization_id, changes["tax_id"])
            if duplicate is not None and duplicate.id != supplier.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier tax ID already exists")
        requested_state = changes.get("is_active")
        if requested_state is not None and requested_state != supplier.is_active:
            action = "SUPPLIER_ACTIVATED" if requested_state else "SUPPLIER_DEACTIVATED"
        else:
            action = "SUPPLIER_UPDATED"
        for field, value in changes.items():
            if field == "email":
                value = str(value) if value else None
            setattr(supplier, field, value)
        supplier.updated_by = actor_id
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action=action),
                entity_type="supplier", entity_id=supplier.id, payload=self._audit_payload(supplier),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier conflicts with existing master data") from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(supplier)
        return supplier
