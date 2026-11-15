"""Pydantic request/response models (input validation at the HTTP boundary)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.users import Administrator, Technician, User


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class RegisterRequest(ApiModel):
    # Format is validated once, in the domain (require_email); EmailStr would reject demo domains like .test
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=30)
    department: str | None = Field(default=None, max_length=80)


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class TechnicianProfileOut(ApiModel):
    skills: list[str]
    experience_years: int
    max_workload: int
    is_available: bool
    is_team_lead: bool
    team: str


class UserOut(ApiModel):
    id: int
    email: str
    full_name: str
    role: str
    code: str
    phone: str | None
    department: str | None
    is_active: bool
    created_at: datetime
    admin_level: str | None = None
    technician_profile: TechnicianProfileOut | None = None

    @classmethod
    def from_domain(cls, user: User) -> "UserOut":
        profile = None
        if isinstance(user, Technician):
            p = user.profile
            profile = TechnicianProfileOut(skills=sorted(p.skills), experience_years=p.experience_years,
                                           max_workload=p.max_workload, is_available=p.is_available,
                                           is_team_lead=p.is_team_lead, team=p.team)
        return cls(
            id=user.id, email=user.email, full_name=user.full_name, role=user.role.value, code=user.display_code,
            phone=user.phone, department=user.department, is_active=user.is_active, created_at=user.created_at,
            admin_level=user.admin_level.value if isinstance(user, Administrator) else None,
            technician_profile=profile,
        )


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
