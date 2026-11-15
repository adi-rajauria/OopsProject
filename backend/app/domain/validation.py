import re

from app.domain.exceptions import InvalidInputError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9 \-]{7,20}$")


def require_text(value: str, field: str, *, min_len: int = 1, max_len: int = 255) -> str:
    cleaned = (value or "").strip()
    if not min_len <= len(cleaned) <= max_len:
        raise InvalidInputError(f"{field} must be between {min_len} and {max_len} characters", details={"field": field})
    return cleaned


def require_range(value: int, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InvalidInputError(f"{field} must be an integer between {low} and {high}", details={"field": field})
    return value


def require_email(value: str) -> str:
    cleaned = (value or "").strip().lower()
    if not _EMAIL_RE.match(cleaned) or len(cleaned) > 255:
        raise InvalidInputError("Invalid email address", details={"field": "email"})
    return cleaned


def optional_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if not _PHONE_RE.match(cleaned):
        raise InvalidInputError("Invalid phone number", details={"field": "phone"})
    return cleaned
