import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.logging_config import configure_logging
from app.services.hunter import scrape_jobs


async def main() -> None:
    configure_logging()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scrape_jobs, "interval", minutes=settings.hunter_interval_minutes)
    scheduler.start()
    await scrape_jobs()
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
