from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.enums.accounting import JournalType
from app.db.base import Base


class Journal(Base):
    """A tenant-scoped accounting journal used to group journal entries."""

    __tablename__ = "journals"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "code", name="uq_journal_organization_code"
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_journals_organization_id_id"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    journal_type = Column(
        SQLEnum(JournalType), nullable=False, default=JournalType.GENERAL
    )
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="journals")
    entries = relationship(
        "JournalEntry", back_populates="journal", foreign_keys="JournalEntry.journal_id"
    )
