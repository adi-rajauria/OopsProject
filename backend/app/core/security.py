from datetime import timedelta

import jwt
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.domain.clock import Clock
from app.domain.exceptions import InvalidTokenError
from app.domain.users import User
from app.services.ports import TokenClaims


class Argon2PasswordHasher:
    """Argon2id with the library's recommended parameters (salted, memory-hard)."""

    def __init__(self) -> None:
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False


class JwtTokenService:
    def __init__(self, secret: str, clock: Clock, *, algorithm: str = "HS256", expiry_minutes: int = 60) -> None:
        self._secret = secret
        self._clock = clock
        self._algorithm = algorithm
        self._expiry = timedelta(minutes=expiry_minutes)

    def issue(self, user: User) -> str:
        now = self._clock.now()
        payload = {"sub": str(user.id), "role": user.role.value, "email": user.email, "iat": now, "exp": now + self._expiry}
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> TokenClaims:
        try:
            # Signature is verified by PyJWT; expiry is checked against our injected Clock so it is testable.
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["exp", "sub", "role", "email"], "verify_exp": False, "verify_iat": False},
            )
            claims = TokenClaims(user_id=int(payload["sub"]), role=str(payload["role"]), email=str(payload["email"]))
            expires_at = float(payload["exp"])
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise InvalidTokenError("Invalid authentication token") from None
        if self._clock.now().timestamp() >= expires_at:
            raise InvalidTokenError("Session expired, please log in again")
        return claims
