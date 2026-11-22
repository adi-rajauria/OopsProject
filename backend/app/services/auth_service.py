import re
from dataclasses import dataclass

from app.domain.clock import Clock
from app.domain.enums import Role
from app.domain.events import EventBus, UserRegistered
from app.domain.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidInputError,
    InvalidTokenError,
)
from app.domain.factories import UserFactory
from app.domain.repositories import UnitOfWork
from app.domain.users import User
from app.domain.validation import require_email
from app.services.ports import PasswordHasher, TokenService

PASSWORD_MIN, PASSWORD_MAX = 8, 128


def validate_password(password: str) -> str:
    if not PASSWORD_MIN <= len(password or "") <= PASSWORD_MAX:
        raise InvalidInputError(
            f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters", details={"field": "password"}
        )
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        raise InvalidInputError(
            "Password must contain at least one letter and one digit", details={"field": "password"}
        )
    return password


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    user: User


class AuthService:
    def __init__(
        self, uow: UnitOfWork, hasher: PasswordHasher, tokens: TokenService, clock: Clock, bus: EventBus
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock
        self._bus = bus
        self._dummy_hash: str | None = None

    def register_employee(
        self, *, email: str, full_name: str, password: str, phone: str | None = None, department: str | None = None
    ) -> User:
        """Self-registration always creates an Employee; staff accounts are created by admins."""
        return self.create_account(
            Role.EMPLOYEE,
            email=email,
            full_name=full_name,
            password=password,
            phone=phone,
            department=department,
            actor_id=None,
        )

    def create_account(
        self,
        role: Role,
        *,
        email: str,
        full_name: str,
        password: str,
        actor_id: int | None,
        phone: str | None = None,
        department: str | None = None,
        **role_specific,
    ) -> User:
        email = require_email(email)
        if self._uow.users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(email)
        user = UserFactory.create(
            role,
            email=email,
            full_name=full_name,
            password_hash=self._hasher.hash(validate_password(password)),
            created_at=self._clock.now(),
            phone=phone,
            department=department,
            **role_specific,
        )
        self._uow.users.add(user)
        self._bus.publish(
            UserRegistered(
                occurred_at=self._clock.now(),
                actor_id=actor_id or user.id,
                user_id=user.id,
                role=user.role.value,
                email=user.email,
            )
        )
        self._uow.commit()
        return user

    def login(self, email: str, password: str) -> LoginResult:
        user = self._uow.users.get_by_email((email or "").strip().lower())
        if user is None:
            self._hasher.verify(self._dummy(), password or "")  # same cost as a real check (no user enumeration)
            raise InvalidCredentialsError()
        if not self._hasher.verify(user.password_hash, password or "") or not user.is_active:
            raise InvalidCredentialsError()
        return LoginResult(self._tokens.issue(user), user)

    def authenticate(self, token: str) -> User:
        claims = self._tokens.decode(token)
        user = self._uow.users.get(claims.user_id)
        # The id alone is not enough: after the data is rebuilt, the same id can belong to a different person.
        if user is None or not user.is_active or user.role.value != claims.role or user.email != claims.email:
            raise InvalidTokenError("Token no longer matches an active account")
        return user

    def _dummy(self) -> str:
        if self._dummy_hash is None:
            self._dummy_hash = self._hasher.hash("dummy-password-1")
        return self._dummy_hash
