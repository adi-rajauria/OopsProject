from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime

from app.domain.enums import AdminLevel, Permission, Role
from app.domain.exceptions import InvalidInputError
from app.domain.validation import optional_phone, require_email, require_range, require_text


class User(ABC):
    """Abstract base for every account.

    Inheritance is used only here because each subclass genuinely *is a* User.
    Encapsulation: state lives in private attributes exposed through read-only
    properties; changes go through intention-revealing methods that validate.
    """

    def __init__(
        self,
        *,
        id: int | None,
        email: str,
        full_name: str,
        password_hash: str,
        created_at: datetime,
        phone: str | None = None,
        department: str | None = None,
        is_active: bool = True,
    ) -> None:
        self._id = id
        self._email = require_email(email)
        self._full_name = require_text(full_name, "full_name", min_len=2, max_len=120)
        self._password_hash = password_hash
        self._phone = optional_phone(phone)
        self._department = department.strip() if department else None
        self._is_active = is_active
        self._created_at = created_at

    # Polymorphism: each subclass answers these differently.
    @property
    @abstractmethod
    def role(self) -> Role: ...

    @abstractmethod
    def permissions(self) -> frozenset[Permission]: ...

    def has_permission(self, permission: Permission) -> bool:
        return self._is_active and permission in self.permissions()

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def email(self) -> str:
        return self._email

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def phone(self) -> str | None:
        return self._phone

    @property
    def department(self) -> str | None:
        return self._department

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def display_code(self) -> str:
        """Short code used in audit text, e.g. E102 / T205 / A3 (matches the spec's examples)."""
        return f"{self.role.value[0]}{self._id}"

    def assign_id(self, new_id: int) -> None:
        if self._id is not None and self._id != new_id:
            raise InvalidInputError("User id is immutable once assigned")
        self._id = new_id

    def update_profile(self, *, full_name: str | None = None, phone: str | None = None,
                       department: str | None = None) -> None:
        if full_name is not None:
            self._full_name = require_text(full_name, "full_name", min_len=2, max_len=120)
        if phone is not None:
            self._phone = optional_phone(phone)
        if department is not None:
            self._department = department.strip() or None

    def change_password_hash(self, new_hash: str) -> None:
        self._password_hash = new_hash

    def activate(self) -> None:
        self._is_active = True

    def deactivate(self) -> None:
        self._is_active = False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and self._id is not None and self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._id))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id}, email={self._email!r})"


class Employee(User):
    _PERMISSIONS = frozenset({Permission.REPORT_INCIDENT})

    @property
    def role(self) -> Role:
        return Role.EMPLOYEE

    def permissions(self) -> frozenset[Permission]:
        return self._PERMISSIONS


@dataclass(frozen=True)
class TechnicianProfile:
    """Value object composed into Technician (no identity of its own)."""

    skills: frozenset[str] = field(default_factory=frozenset)
    experience_years: int = 0
    max_workload: int = 8
    is_available: bool = True
    is_team_lead: bool = False
    team: str = "General"

    def __post_init__(self) -> None:
        require_range(self.experience_years, "experience_years", 0, 60)
        require_range(self.max_workload, "max_workload", 1, 50)
        object.__setattr__(self, "skills", frozenset(s.strip().upper() for s in self.skills if s.strip()))
        object.__setattr__(self, "team", require_text(self.team, "team", max_len=60))


class Technician(User):
    _PERMISSIONS = frozenset(
        {Permission.REPORT_INCIDENT, Permission.VIEW_ALL_INCIDENTS, Permission.WORK_INCIDENTS}
    )

    def __init__(self, *, profile: TechnicianProfile | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._profile = profile or TechnicianProfile()

    @property
    def role(self) -> Role:
        return Role.TECHNICIAN

    def permissions(self) -> frozenset[Permission]:
        return self._PERMISSIONS

    @property
    def profile(self) -> TechnicianProfile:
        return self._profile

    def has_skill(self, category_code: str | None) -> bool:
        return category_code is not None and category_code.upper() in self._profile.skills

    def can_accept_more(self, active_incidents: int) -> bool:
        return self._profile.is_available and self.is_active and active_incidents < self._profile.max_workload

    def update_technician_profile(self, **changes) -> None:
        self._profile = replace(self._profile, **changes)

    def set_availability(self, available: bool) -> None:
        self._profile = replace(self._profile, is_available=available)


class Administrator(User):
    _PERMISSIONS = frozenset(Permission)

    def __init__(self, *, admin_level: AdminLevel = AdminLevel.SYSTEM_ADMIN, **kwargs) -> None:
        super().__init__(**kwargs)
        self._admin_level = admin_level

    @property
    def role(self) -> Role:
        return Role.ADMINISTRATOR

    def permissions(self) -> frozenset[Permission]:
        return self._PERMISSIONS

    @property
    def admin_level(self) -> AdminLevel:
        return self._admin_level

    def set_admin_level(self, level: AdminLevel) -> None:
        self._admin_level = level
