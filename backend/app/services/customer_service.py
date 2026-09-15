from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.audit_context import AuditContext
from app.models.customer import Customer
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CustomerRepository(session)
        self.audit_repository = AuditLogRepository(session)

    @staticmethod
    def _audit_payload(customer: Customer) -> dict:
        return {
            "customer_id": customer.id,
            "code": customer.code,
            "legal_name": customer.legal_name,
            "trade_name": customer.trade_name,
            "tax_id": customer.tax_id,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
            "is_active": customer.is_active,
        }

    @staticmethod
    def _update_audit_action(customer: Customer, changes: dict) -> str:
        """Return a lifecycle-specific action when the active state changes."""
        if "is_active" in changes and changes["is_active"] is not None:
            requested_state = changes["is_active"]
            if requested_state != customer.is_active:
                return "CUSTOMER_ACTIVATED" if requested_state else "CUSTOMER_DEACTIVATED"
        return "CUSTOMER_UPDATED"

    async def get(self, organization_id: str, customer_id: str) -> Customer:
        customer = await self.repository.get_by_id(organization_id, customer_id)
        if customer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return customer

    async def list(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> list[Customer]:
        return await self.repository.list(
            organization_id,
            skip=skip,
            limit=limit,
            is_active=is_active,
        )

    async def create(self, organization_id: str, actor_id: str, data: CustomerCreate) -> Customer:
        if await self.repository.get_by_code(organization_id, data.code):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer code already exists")
        if data.tax_id and await self.repository.get_by_tax_id(organization_id, data.tax_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer tax ID already exists")

        customer = Customer(
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
        self.repository.add(customer)
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(
                    organization_id=organization_id,
                    actor_id=actor_id,
                    action="CUSTOMER_CREATED",
                ),
                entity_type="customer",
                entity_id=customer.id,
                payload=self._audit_payload(customer),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer conflicts with existing master data") from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(customer)
        return customer

    async def update(
        self,
        organization_id: str,
        customer_id: str,
        actor_id: str,
        data: CustomerUpdate,
    ) -> Customer:
        customer = await self.get(organization_id, customer_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return customer

        if "tax_id" in changes and changes["tax_id"]:
            duplicate = await self.repository.get_by_tax_id(organization_id, changes["tax_id"])
            if duplicate is not None and duplicate.id != customer.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer tax ID already exists")

        audit_action = self._update_audit_action(customer, changes)
        for field, value in changes.items():
            if field == "email":
                value = str(value) if value else None
            setattr(customer, field, value)
        customer.updated_by = actor_id

        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(
                    organization_id=organization_id,
                    actor_id=actor_id,
                    action=audit_action,
                ),
                entity_type="customer",
                entity_id=customer.id,
                payload=self._audit_payload(customer),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer conflicts with existing master data") from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(customer)
        return customer
