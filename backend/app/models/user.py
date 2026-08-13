"""Persistent user identity, independent from a selected tenant."""

from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)

    memberships = relationship(
        "OrganizationMembership", back_populates="user", cascade="all, delete-orphan"
    )
