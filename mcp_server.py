from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer
from sqlalchemy import select

from app.models.job import Job
from app.models.resume import Resume
from app.services.cv_generator import generate_tailored_cv
from app.services.database import AsyncSessionLocal
from app.services.matcher import score_resume_against_job

mcp = MCPServer(name="jobscout", version="0.1.0")


@mcp.tool()
async def search_jobs(keyword: str = "", location: str = "", limit: int = 20) -> str:
    """Search stored jobs by title, company, description, or location."""
    limit = max(1, min(limit, 100))
    async with AsyncSessionLocal() as db:
        query = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if keyword:
            pattern = f"%{keyword}%"
            query = query.where(Job.title.ilike(pattern) | Job.company.ilike(pattern) | Job.description.ilike(pattern))
        if location:
            query = query.where(Job.location.ilike(f"%{location}%"))
        jobs = (await db.execute(query)).scalars().all()
    return json.dumps([{"id": j.id, "title": j.title, "company": j.company, "location": j.location, "url": j.url} for j in jobs])


@mcp.tool()
async def match_resume(resume_id: int, limit: int = 10) -> str:
    """Score a stored resume against the newest unflagged jobs."""
    async with AsyncSessionLocal() as db:
        resume = (await db.execute(select(Resume).where(Resume.id == resume_id))).scalars().first()
        jobs = (await db.execute(select(Job).where(Job.flagged.is_(False)).order_by(Job.created_at.desc()).limit(50))).scalars().all()
    if not resume:
        return json.dumps({"error": "resume not found"})
    scored = []
    for job in jobs:
        result = await score_resume_against_job(resume.content, job.title, job.company, job.experience_required, job.description)
        scored.append({"job_id": job.id, "title": job.title, "company": job.company, "url": job.url, **result})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return json.dumps(scored[:max(1, min(limit, 50))])


@mcp.tool()
async def tailor_cv(resume_id: int, job_id: int) -> str:
    """Generate a truthful tailored CV for a stored resume and job."""
    async with AsyncSessionLocal() as db:
        resume = (await db.execute(select(Resume).where(Resume.id == resume_id))).scalars().first()
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalars().first()
    if not resume or not job:
        return json.dumps({"error": "resume or job not found"})
    cv = await generate_tailored_cv(resume.content, job.title, job.company, job.experience_required, job.description)
    return json.dumps({"resume_id": resume_id, "job_id": job_id, "cv": cv})


if __name__ == "__main__":
    import asyncio

    asyncio.run(mcp.run_stdio_async())
