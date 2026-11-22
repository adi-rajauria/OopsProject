import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.api import admin, auth, health, incidents, intelligence, lookups, notifications, reports, stream, technicians
from app.core.config import Settings, get_settings
from app.core.db import make_engine, make_session_factory
from app.core.errors import register_error_handlers
from app.core.security import Argon2PasswordHasher, JwtTokenService
from app.domain.clock import Clock, SystemClock
from app.notifications.channels import ChannelRegistry, EmailChannel, InAppChannel, SMSChannel
from app.notifications.providers import FakeSmsGateway, FakeSmtpProvider
from app.realtime.broadcaster import EventBroadcaster
from app.services.container import Infrastructure
from app.workers.sla_monitor import SLAMonitor

ROUTERS = (health, auth, incidents, intelligence, technicians, notifications, reports, lookups, admin, stream)


def build_infrastructure(settings: Settings, clock: Clock | None = None) -> Infrastructure:
    clock = clock or SystemClock()
    channels = ChannelRegistry(
        [
            InAppChannel(),
            EmailChannel(FakeSmtpProvider(fail=settings.simulate_email_failure)),
            SMSChannel(FakeSmsGateway(fail=settings.simulate_sms_failure)),
        ]
    )
    tokens = JwtTokenService(
        settings.jwt_secret.get_secret_value(),
        clock,
        algorithm=settings.jwt_algorithm,
        expiry_minutes=settings.jwt_expiry_minutes,
    )
    return Infrastructure(
        clock=clock, hasher=Argon2PasswordHasher(), tokens=tokens, channels=channels, broadcaster=EventBroadcaster()
    )


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Starts the background SLA monitor (one asyncio task in this process)."""
    settings: Settings = app.state.settings
    task = None
    if settings.sla_monitor_enabled:
        task = asyncio.create_task(app.state.sla_monitor.run_forever())
    yield
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
    infra: Infrastructure | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = FastAPI(
        title="Decerno API",
        version="1.0.0",
        lifespan=lifespan,
        description="Intelligent IT Service Management & Incident Resolution System",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory or make_session_factory(make_engine(settings.database_url))
    app.state.infra = infra or build_infrastructure(settings)
    app.state.sla_monitor = SLAMonitor(app.state.session_factory, app.state.infra, settings.sla_check_interval_seconds)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    for module in ROUTERS:
        app.include_router(module.router)
    return app
