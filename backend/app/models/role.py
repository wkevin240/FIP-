"""Optional extensible role catalog used by administration tooling."""

from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.orm import relationship

from app.db.base import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "permission_id",
        String,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    is_system = Column(Boolean, nullable=False, default=True)
    permissions = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )
