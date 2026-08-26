from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class ClosingSignoff(Base):
    __tablename__ = "closing_signoffs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "fiscal_year_id",
            name="uq_closing_signoff_organization_year",
        ),
        ForeignKeyConstraint(
            ["organization_id", "fiscal_year_id"],
            ["fiscal_years.organization_id", "fiscal_years.id"],
            name="fk_closing_signoff_organization_year",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('SIGNED', 'REVOKED')",
            name="ck_closing_signoff_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiscal_year_id = Column(
        String,
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(String(16), nullable=False, default="SIGNED")
    signed_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    signed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    control_hash = Column(String(64), nullable=False)
    control_snapshot = Column(String, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
