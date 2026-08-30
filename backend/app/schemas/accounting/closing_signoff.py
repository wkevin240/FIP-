from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClosingSignoffResponse(BaseModel):
    id: str
    organization_id: str
    fiscal_year_id: str
    status: str
    signed_by_user_id: str
    signed_at: datetime
    control_hash: str
    control_snapshot: str
    revoked_at: datetime | None = None
    revoked_by_user_id: str | None = None

    model_config = ConfigDict(from_attributes=True)
