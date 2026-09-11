from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.base import Base


class AuditLog(Base):
    """Durable, append-only representation of an in-process audit record."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        UniqueConstraint("organization_id", "sequence_no", name="uq_audit_log_organization_sequence"),
        UniqueConstraint("organization_id", "record_hash", name="uq_audit_log_organization_hash"),
        CheckConstraint("sequence_no > 0", name="ck_audit_log_sequence_positive"),
    )

    organization_id = Column(String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    sequence_no = Column(Integer, nullable=False)
    actor_id = Column(String, nullable=False)
    action = Column(String(128), nullable=False)
    entity_type = Column(String(255), nullable=False)
    entity_id = Column(String(255), nullable=False)
    payload_json = Column(Text, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    previous_hash = Column(String(64), nullable=True)
    record_hash = Column(String(64), nullable=False)
    request_id = Column(String(255), nullable=True)
