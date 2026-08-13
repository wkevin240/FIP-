"""Explicit permission catalog for role-based access control."""

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.role import role_permissions


class Permission(Base):
    __tablename__ = "permissions"

    code = Column(String(128), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    roles = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )
