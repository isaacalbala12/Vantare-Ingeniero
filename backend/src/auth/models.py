"""Modelos de datos para el sistema de autenticación."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LicenseDB(BaseModel):
    key: str
    user_email: Optional[str] = None
    is_active: bool = True
    created_at: datetime = datetime.now()
    expires_at: Optional[datetime] = None


class UserDB(BaseModel):
    id: Optional[int] = None
    email: str
    google_sub: Optional[str] = None
    created_at: datetime = datetime.now()


class UsageLogDB(BaseModel):
    id: Optional[int] = None
    license_key: str
    endpoint: str
    tokens_in: int = 0
    tokens_out: int = 0
    timestamp: datetime = datetime.now()
