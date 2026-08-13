from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.membership import OrganizationMembership
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import LoginRequest, UserCreate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserRepository(session)

    async def create(self, data: UserCreate) -> User:
        email = str(data.email).lower()
        if await self.repository.get_by_email(email):
            raise ValueError("Email already exists")
        user = User(email=email, full_name=data.full_name, hashed_password=get_password_hash(data.password))
        await self.repository.create(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def add_membership(self, user_id: str, organization_id: str, role: str) -> OrganizationMembership:
        if await self.repository.get_membership(user_id, organization_id):
            raise ValueError("User is already a member of this organization")
        membership = OrganizationMembership(user_id=user_id, organization_id=organization_id, role=role)
        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)
        return membership

    async def authenticate(self, data: LoginRequest) -> str:
        user = await self.repository.get_by_email(str(data.email))
        if user is None or not user.is_active or not verify_password(data.password, user.hashed_password):
            raise ValueError("Invalid credentials")
        membership = await self.repository.get_membership(user.id, data.organization_id)
        if membership is None or not membership.is_active:
            raise ValueError("Organization access denied")
        return create_access_token(user.id, membership.organization_id)
