from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.db.base import Base


class AuditSequence(Base):
    __tablename__ = "audit_sequences"

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    last_sequence = Column(Integer, nullable=False, default=0)
    last_hash = Column(String(64), nullable=False, default="0" * 64)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("sequence_number > 0", name="ck_audit_event_sequence_positive"),
        CheckConstraint("action <> ''", name="ck_audit_event_action_not_empty"),
        CheckConstraint(
            "resource_type <> ''", name="ck_audit_event_resource_type_not_empty"
        ),
        CheckConstraint(
            "resource_id <> ''", name="ck_audit_event_resource_id_not_empty"
        ),
        CheckConstraint("length(event_hash) = 64", name="ck_audit_event_hash_length"),
        CheckConstraint(
            "length(previous_hash) = 64", name="ck_audit_event_previous_hash_length"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence_number = Column(Integer, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    actor_user_id = Column(String, nullable=True, index=True)
    action = Column(String(96), nullable=False, index=True)
    resource_type = Column(String(96), nullable=False, index=True)
    resource_id = Column(String, nullable=False, index=True)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
    transaction_id = Column(String(96), nullable=True, index=True)
    request_id = Column(String(96), nullable=True, index=True)
    previous_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False, unique=True)
