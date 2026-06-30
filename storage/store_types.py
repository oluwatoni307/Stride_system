# PATH: stride_backend/storage/store_types.py
# DOMAIN: Shared return types for all storage operations across raw and distilled stores.

from __future__ import annotations

from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class StoreError(BaseModel):
    code: str       # Valid values: NOT_FOUND | ALREADY_EXISTS | READ_ERROR | WRITE_ERROR
    message: str
    operation: str


class StoreResult(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[StoreError] = None