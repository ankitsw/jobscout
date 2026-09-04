import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.database import get_db
from app.models.resume import Resume
from app.models.job import Job
from app.schemas.match import MatchRequest, JobMatchOut
from app.services.matcher import score_resume_against_job

router = APIRouter(prefix="/match", tags=["match"])


@router.post("/", response_model=list[JobMatchOut])
async def match_resume_to_jobs(request: MatchRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).where(Resume.id == request.resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if request.job_ids:
        result = await db.execute(select(Job).where(Job.id.in_(request.job_ids)))
    else:
        result = await db.execute(select(Job).where(Job.flagged == False))
    jobs = result.scalars().all()

    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found to match against")

    async def score_job(job) -> JobMatchOut | None:
        try:
            result = await score_resume_against_job(
                resume_content=resume.content,
                job_title=job.title,
                company=job.company,
                experience_required=job.experience_required,
                job_description=job.description,
            )
        except ValueError:
            return None
        return JobMatchOut(
            job_id=job.id,
            title=job.title,
            company=job.company,
            location=job.location,
            url=job.url,
            platform=job.platform,
            **result,
        )

    scored = await asyncio.gather(*[score_job(job) for job in jobs])
    matches = [m for m in scored if m is not None]
    matches.sort(key=lambda x: x.score, reverse=True)
    return matches
