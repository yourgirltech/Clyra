from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ClaimOut(BaseModel):
    id: int
    claim_id: str
    clinic_id: int
    payer_id: int
    payer_name: Optional[str]
    patient_id: Optional[int]
    patient_name: Optional[str]
    amount: float
    status: str
    risk_level: str
    risk_score: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ClaimListQuery(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=200)
    status: Optional[str]
    risk_level: Optional[str]
    payer_id: Optional[int]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    search: Optional[str]


class ClaimListResponse(BaseModel):
    items: list[ClaimOut]
    total: int
    page: int
    size: int

    class Config:
        orm_mode = True
