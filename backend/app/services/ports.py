"""Interfaces the services need from infrastructure (implemented in app/core/security.py)."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.users import User


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    role: str


class TokenService(Protocol):
    def issue(self, user: User) -> str: ...

    def decode(self, token: str) -> TokenClaims:
        """Raises InvalidTokenError if the token is malformed, tampered or expired."""
        ...
