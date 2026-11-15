import pytest

from app.core.security import Argon2PasswordHasher, JwtTokenService
from app.domain.enums import Role
from app.domain.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidInputError,
    InvalidTokenError,
)
from tests.conftest import FakeClock


def test_register_login_and_authenticate(world):
    auth = world.container.auth
    user = auth.register_employee(email="New.User@Corp.test", full_name="New User", password="Secret123")
    assert user.role is Role.EMPLOYEE and user.email == "new.user@corp.test"
    result = auth.login("new.user@corp.test", "Secret123")
    assert auth.authenticate(result.access_token) == user
    assert world.uow.audit.list_recent(action="USER_CREATED")[0].description == \
        "Employee account new.user@corp.test created"


@pytest.mark.parametrize("password", ["short1", "lettersonly", "12345678"])
def test_weak_passwords_are_rejected(world, password):
    with pytest.raises(InvalidInputError):
        world.container.auth.register_employee(email="weak@corp.test", full_name="Weak Pw", password=password)


def test_duplicate_email_is_rejected(world):
    with pytest.raises(EmailAlreadyRegisteredError):
        world.container.auth.register_employee(email="EMP@corp.test", full_name="Dup", password="Secret123")


@pytest.mark.parametrize(("email", "password"), [("emp@corp.test", "wrong-pass1"), ("ghost@corp.test", "Password1")])
def test_invalid_login(world, email, password):
    with pytest.raises(InvalidCredentialsError):
        world.container.auth.login(email, password)


def test_deactivated_user_cannot_log_in_or_use_old_token(world):
    auth = world.container.auth
    token = auth.login("emp@corp.test", "Password1").access_token
    world.employee.deactivate()
    with pytest.raises(InvalidCredentialsError):
        auth.login("emp@corp.test", "Password1")
    with pytest.raises(InvalidTokenError):
        auth.authenticate(token)


def test_tampered_and_expired_tokens_are_rejected(world):
    clock = FakeClock()
    tokens = JwtTokenService("k" * 40, clock, expiry_minutes=60)
    token = tokens.issue(world.employee)
    assert tokens.decode(token).user_id == world.employee.id
    with pytest.raises(InvalidTokenError):
        JwtTokenService("x" * 40, clock).decode(token)  # signed with another key
    with pytest.raises(InvalidTokenError):
        tokens.decode(token[:-3] + "abc")
    clock.advance(minutes=60)
    with pytest.raises(InvalidTokenError):
        tokens.decode(token)


def test_argon2_hashes_are_salted_and_verifiable():
    hasher = Argon2PasswordHasher()
    first, second = hasher.hash("Secret123"), hasher.hash("Secret123")
    assert first != second and first.startswith("$argon2id$")
    assert hasher.verify(first, "Secret123") and not hasher.verify(first, "secret123")
    assert not hasher.verify("not-a-hash", "Secret123")
