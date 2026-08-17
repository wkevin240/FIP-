from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryAccountingProfileCreate(BaseModel):
    journal_id: str = Field(min_length=1)
    inventory_account_id: str = Field(min_length=1)
    receipt_counterpart_account_id: str = Field(min_length=1)
    cost_of_sales_account_id: str = Field(min_length=1)
    adjustment_gain_account_id: str = Field(min_length=1)
    adjustment_loss_account_id: str = Field(min_length=1)
    is_active: bool = True


class InventoryAccountingProfileResponse(InventoryAccountingProfileCreate):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryAccountingPostingResponse(BaseModel):
    id: str
    organization_id: str
    source_module: str
    source_type: str
    source_id: str
    journal_entry_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
