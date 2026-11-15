from fastapi import APIRouter, status

from app.api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.core.deps import Container, CurrentUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, container: Container) -> UserOut:
    user = container.auth.register_employee(email=body.email, full_name=body.full_name, password=body.password,
                                            phone=body.phone, department=body.department)
    return UserOut.from_domain(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, container: Container) -> TokenResponse:
    result = container.auth.login(body.email, body.password)
    return TokenResponse(access_token=result.access_token, user=UserOut.from_domain(result.user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.from_domain(user)
