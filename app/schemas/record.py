from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.record import RecordType


class RecordBase(BaseModel):
    amount: Decimal = Field(gt=0)
    type: RecordType
    category: str = Field(min_length=1, max_length=120)
    date: date
    notes: Optional[str] = Field(default=None, max_length=2000)


class RecordCreate(RecordBase):
    user_id: Optional[str] = None


class RecordUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0)
    type: Optional[RecordType] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=120)
    date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class RecordRead(RecordBase):
    model_config = {
        "from_attributes": True,
    }

    id: UUID
    user_id: UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class RecordFilter(BaseModel):
    type: Optional[RecordType] = None
    category: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class RecordListResponse(BaseModel):
    items: List[RecordRead]
    total: int
    page: int
    page_size: int
