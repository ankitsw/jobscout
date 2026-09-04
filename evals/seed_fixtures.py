"""Seed the database with the exact jobs/resume rows the golden set
references, so run_retrieval_eval.py is reproducible without depending
on live scraped data that can drift or get deleted.

Usage: python -m evals.seed_fixtures
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.services.database import AsyncSessionLocal
from app.models.job import Job
from app.models.resume import Resume

FIXTURES = Path(__file__).parent / "fixtures"


async def run() -> None:
    jobs = json.loads((FIXTURES / "jobs.json").read_text())
    resumes = json.loads((FIXTURES / "resumes.json").read_text())

    async with AsyncSessionLocal() as db:
        for row in jobs:
            stmt = insert(Job).values(**row).on_conflict_do_update(index_elements=["id"], set_=row)
            await db.execute(stmt)
        for row in resumes:
            stmt = insert(Resume).values(**row).on_conflict_do_update(index_elements=["id"], set_=row)
            await db.execute(stmt)
        await db.commit()
    print(f"seeded {len(jobs)} jobs, {len(resumes)} resumes")


if __name__ == "__main__":
    asyncio.run(run())
