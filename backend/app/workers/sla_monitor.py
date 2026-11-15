"""Background SLA monitor: every N seconds detect warnings, breaches and escalations."""

import asyncio
import logging

from sqlalchemy.orm import Session, sessionmaker

from app.repositories.sql_repositories import SqlAlchemyUnitOfWork
from app.services.container import Infrastructure, build_container
from app.services.sla_service import SLACheckSummary

logger = logging.getLogger(__name__)


class SLAMonitor:
    def __init__(self, session_factory: sessionmaker[Session], infra: Infrastructure, interval_seconds: int) -> None:
        self._session_factory = session_factory
        self._infra = infra
        self._interval = interval_seconds

    def run_once(self) -> SLACheckSummary:
        """One pass in its own session/transaction (also used by the admin 'check now' button)."""
        with self._session_factory() as session:
            container = build_container(SqlAlchemyUnitOfWork(session, self._infra.clock), self._infra)
            return container.sla.run_checks()

    async def run_forever(self) -> None:
        logger.info("SLA monitor started (every %d s)", self._interval)
        while True:
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:  # keep monitoring even if one pass fails (e.g. DB restart)
                logger.exception("SLA monitor pass failed")
            await asyncio.sleep(self._interval)
