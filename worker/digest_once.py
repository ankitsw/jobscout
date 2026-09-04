import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.logging_config import configure_logging
from app.models.job import Job
from app.services.database import AsyncSessionLocal
from app.services.emailer import send_digest


async def main() -> None:
    configure_logging()
    since = datetime.now(timezone.utc) - timedelta(days=1)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Job).where(Job.created_at >= since).order_by(Job.created_at.desc()))
        jobs = result.scalars().all()
    alerts = [{
        "job_title": job.title,
        "company": job.company,
        "location": job.location,
        "posted_at": job.posted_at,
        "job_url": job.url,
        "match_score": "-",
    } for job in jobs]
    await send_digest(alerts)
    logging.getLogger(__name__).info("digest complete", extra={"jobs": len(alerts)})


if __name__ == "__main__":
    asyncio.run(main())
