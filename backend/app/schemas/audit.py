from pydantic import BaseModel


class AuditChainVerificationResponse(BaseModel):
    organization_id: str
    valid: bool
    record_count: int
