"""Memberships bind a user, a tenant organization and an application role."""

from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.enums.users import MembershipRole
from app.db.base import Base


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", name="uq_membership_user_organization"
        ),
    )

    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False, default=MembershipRole.USER.value)
    is_active = Column(Boolean, nullable=False, default=True)

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")
