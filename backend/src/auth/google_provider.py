"""Proveedor Google OAuth — stub para futuro."""
from src.auth.protocol import AuthProvider, ProviderResult


class GoogleProvider(AuthProvider):
    async def validate(self, token: str) -> ProviderResult:
        raise NotImplementedError("Google OAuth not yet implemented")
