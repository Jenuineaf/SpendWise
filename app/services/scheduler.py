import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services.recurring_service import materialize_due_expenses

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_materialize_job() -> None:
    async with AsyncSessionLocal() as db:
        created = await materialize_due_expenses(db)
        if created:
            logger.info("Materialized %d recurring expense(s)", created)


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.add_job(
            _run_materialize_job,
            "interval",
            hours=1,
            id="materialize_recurring",
            replace_existing=True,
        )
        scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
