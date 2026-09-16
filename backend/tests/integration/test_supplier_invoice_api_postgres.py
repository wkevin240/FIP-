import os
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.dependencies import get_db
from app.core.enums.users import MembershipRole
from app.core.security import create_access_token
from app.main import create_application
from app.models.audit.audit_log import AuditLog
from app.models.membership import OrganizationMembership
from app.models.organization import Organization
from app.models.supplier import Supplier
from app.models.user import User


@pytest.mark.asyncio
async def test_supplier_invoice_api_preserves_workflow_and_tenant_boundary() -> None:
    server = os.getenv("POSTGRES_SERVER")
    if not server:
        pytest.skip("PostgreSQL integration environment is not configured")

    database_uri = (
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'fip_user')}"
        f":{os.getenv('POSTGRES_PASSWORD', 'fip_password')}@{server}"
        f":{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'fip_db')}"
    )
    engine = create_async_engine(database_uri, pool_pre_ping=True)

    organization_id = "supplier-invoice-api-org"
    other_organization_id = "supplier-invoice-api-other-org"
    creator_id = "supplier-invoice-api-creator"
    approver_id = "supplier-invoice-api-approver"
    other_actor_id = "supplier-invoice-api-other-actor"
    supplier_id = "supplier-invoice-api-supplier"

    application = create_application()

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_get_db():
            yield session

        application.dependency_overrides[get_db] = override_get_db

        try:
            session.add_all(
                [
                    Organization(id=organization_id, name="supplier-invoice-api-org"),
                    Organization(id=other_organization_id, name="supplier-invoice-api-other-org"),
                    User(
                        id=creator_id,
                        email="supplier-invoice-api-creator@example.invalid",
                        hashed_password="integration-only",
                        is_active=True,
                        is_superuser=False,
                    ),
                    User(
                        id=approver_id,
                        email="supplier-invoice-api-approver@example.invalid",
                        hashed_password="integration-only",
                        is_active=True,
                        is_superuser=False,
                    ),
                    User(
                        id=other_actor_id,
                        email="supplier-invoice-api-other-actor@example.invalid",
                        hashed_password="integration-only",
                        is_active=True,
                        is_superuser=False,
                    ),
                    OrganizationMembership(
                        user_id=creator_id,
                        organization_id=organization_id,
                        role=MembershipRole.ACCOUNTANT.value,
                        is_active=True,
                    ),
                    OrganizationMembership(
                        user_id=approver_id,
                        organization_id=organization_id,
                        role=MembershipRole.MANAGER.value,
                        is_active=True,
                    ),
                    OrganizationMembership(
                        user_id=other_actor_id,
                        organization_id=other_organization_id,
                        role=MembershipRole.MANAGER.value,
                        is_active=True,
                    ),
                    Supplier(
                        id=supplier_id,
                        organization_id=organization_id,
                        code="API-SUP-001",
                        legal_name="API Contract Supplier",
                        is_active=True,
                        created_by=creator_id,
                        updated_by=creator_id,
                    ),
                ]
            )
            await session.flush()

            creator_token = create_access_token(creator_id, organization_id)
            approver_token = create_access_token(approver_id, organization_id)
            other_tenant_token = create_access_token(other_actor_id, other_organization_id)
            payload = {
                "supplier_id": supplier_id,
                "invoice_number": "API-INV-001",
                "invoice_date": "2026-09-15",
                "due_date": "2026-10-15",
                "currency_code": "XAF",
                "subtotal": "1000.00",
                "tax_amount": "180.00",
                "total_amount": "1180.00",
                "description": "API contract integration proof",
            }

            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                created_response = await client.post(
                    "/api/v1/supplier-invoices/",
                    json=payload,
                    headers={"Authorization": f"Bearer {creator_token}"},
                )
                assert created_response.status_code == 201, created_response.text
                created = created_response.json()
                assert created["organization_id"] == organization_id
                assert created["status"] == "DRAFT"
                assert created["created_by"] == creator_id
                assert created["approved_by"] is None
                invoice_id = created["id"]

                self_approval = await client.post(
                    f"/api/v1/supplier-invoices/{invoice_id}/approve",
                    headers={"Authorization": f"Bearer {creator_token}"},
                )
                assert self_approval.status_code == 403
                assert "creator cannot approve" in self_approval.json()["detail"]

                approved_response = await client.post(
                    f"/api/v1/supplier-invoices/{invoice_id}/approve",
                    headers={"Authorization": f"Bearer {approver_token}"},
                )
                assert approved_response.status_code == 200, approved_response.text
                approved = approved_response.json()
                assert approved["status"] == "APPROVED"
                assert approved["approved_by"] == approver_id
                assert Decimal(approved["total_amount"]) == Decimal("1180.00")

                other_tenant_read = await client.get(
                    f"/api/v1/supplier-invoices/{invoice_id}",
                    headers={"Authorization": f"Bearer {other_tenant_token}"},
                )
                assert other_tenant_read.status_code == 404

                aging = await client.get(
                    "/api/v1/supplier-invoices/aging",
                    params={"as_of_date": "2026-10-20"},
                    headers={"Authorization": f"Bearer {approver_token}"},
                )
                assert aging.status_code == 200, aging.text
                rows = aging.json()["rows"]
                assert rows == [
                    {
                        "supplier_id": supplier_id,
                        "supplier_name": "API Contract Supplier",
                        "currency_code": "XAF",
                        "current_amount": "0.00",
                        "overdue_1_30_amount": "1180.00",
                        "overdue_31_60_amount": "0.00",
                        "overdue_61_90_amount": "0.00",
                        "overdue_90_plus_amount": "0.00",
                        "total_amount": "1180.00",
                    }
                ]

            audit_rows = list(
                await session.scalars(
                    select(AuditLog)
                    .where(
                        AuditLog.organization_id == organization_id,
                        AuditLog.entity_type == "supplier_invoice",
                        AuditLog.entity_id == invoice_id,
                    )
                    .order_by(AuditLog.sequence_no)
                )
            )
            assert [row.action for row in audit_rows] == [
                "SUPPLIER_INVOICE_CREATED",
                "SUPPLIER_INVOICE_APPROVED",
            ]
            assert all(row.actor_id in {creator_id, approver_id} for row in audit_rows)
        finally:
            application.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
            await engine.dispose()
