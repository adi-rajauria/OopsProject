import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.api import auth, health
from app.core.config import Settings, get_settings
from app.core.db import make_engine, make_session_factory
from app.core.errors import register_error_handlers
from app.core.security import Argon2PasswordHasher, JwtTokenService
from app.domain.clock import Clock, SystemClock
from app.notifications.channels import ChannelRegistry, EmailChannel, InAppChannel, SMSChannel
from app.notifications.providers import FakeSmsGateway, FakeSmtpProvider
from app.services.container import Infrastructure


def build_infrastructure(settings: Settings, clock: Clock | None = None) -> Infrastructure:
    clock = clock or SystemClock()
    channels = ChannelRegistry([
        InAppChannel(),
        EmailChannel(FakeSmtpProvider(fail=settings.simulate_email_failure)),
        SMSChannel(FakeSmsGateway(fail=settings.simulate_sms_failure)),
    ])
    tokens = JwtTokenService(settings.jwt_secret.get_secret_value(), clock, algorithm=settings.jwt_algorithm,
                             expiry_minutes=settings.jwt_expiry_minutes)
    return Infrastructure(clock=clock, hasher=Argon2PasswordHasher(), tokens=tokens, channels=channels)


def create_app(settings: Settings | None = None, *, session_factory: sessionmaker[Session] | None = None,
               infra: Infrastructure | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = FastAPI(title="I-ITSM API", version="1.0.0",
                  description="Intelligent IT Service Management & Incident Resolution System")
    app.state.settings = settings
    app.state.session_factory = session_factory or make_session_factory(make_engine(settings.database_url))
    app.state.infra = infra or build_infrastructure(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    return app
