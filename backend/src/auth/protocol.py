"""Protocolo de autenticación. Define la interfaz AuthProvider."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderResult:
    is_valid: bool
    error_code: Optional[str] = None  # invalid_key, expired, revoked, server_error
    license_key: Optional[str] = None
    user_email: Optional[str] = None


class AuthProvider(ABC):
    @abstractmethod
    async def validate(self, token: str) -> ProviderResult:
        """Valida un token de autenticación (license key o Google OAuth token).

        Returns:
            ProviderResult con is_valid=True si es válido,
            o is_valid=False con error_code descriptivo si no.
        """
        ...
