import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.database import get_db
from app.models.resume import Resume
from app.models.job import Job
from app.schemas.match import MatchRequest, JobMatchOut
from app.services.embeddings import embed
from app.services.matcher import score_resume_against_job

router = APIRouter(prefix="/match", tags=["match"])


@router.get("/quick")
async def quick_match_scores(resume_id: int, db: AsyncSession = Depends(get_db)) -> dict[int, int]:
    """Cheap, resume-scoped relevance signal for every job in one request -
    pure embedding cosine similarity, no LLM call, so it's fast and free
    enough to run against the whole job list (unlike POST /, which spends
    one Groq call per job and is meant for a small, deliberate shortlist).
    Score is min-max normalised against the current job set, since raw
    cosine similarity between a resume and unrelated postings clusters in a
    narrow band that isn't meaningful as an absolute percentage - what
    matters here is relative ranking within what's actually being compared.
    """
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume_embedding = embed(resume.content)

    result = await db.execute(select(Job.id, Job.embedding))
    similarities: dict[int, float] = {}
    for job_id, job_embedding in result.all():
        if job_embedding is None:
            continue
        similarities[job_id] = sum(a * b for a, b in zip(resume_embedding, job_embedding))

    if not similarities:
        return {}

    lo = min(similarities.values())
    hi = max(similarities.values())
    spread = (hi - lo) or 1.0
    return {job_id: round(100 * (sim - lo) / spread) for job_id, sim in similarities.items()}


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
