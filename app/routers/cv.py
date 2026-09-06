from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.rate_limit import limiter
from app.services.database import get_db
from app.models.resume import Resume
from app.models.job import Job
from app.models.generated_cv import GeneratedCv
from app.services.cv_generator import generate_tailored_cv

router = APIRouter(prefix="/cv", tags=["cv"])


class CVRequest(BaseModel):
    resume_id: int
    job_id: int


@router.get("/")
async def get_saved_cv(resume_id: int, job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GeneratedCv).where(GeneratedCv.resume_id == resume_id, GeneratedCv.job_id == job_id)
    )
    saved = result.scalars().first()
    if not saved:
        raise HTTPException(status_code=404, detail="No saved CV for this resume/job pair")
    return {"resume_id": resume_id, "job_id": job_id, "cv": saved.content}


@router.post("/generate")
@limiter.limit("10/minute")
async def generate_cv(request: Request, payload: CVRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).where(Resume.id == payload.resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    result = await db.execute(select(Job).where(Job.id == payload.job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cv = await generate_tailored_cv(
        resume_content=resume.content,
        job_title=job.title,
        company=job.company,
        experience_required=job.experience_required,
        job_description=job.description,
    )

    result = await db.execute(
        select(GeneratedCv).where(
            GeneratedCv.resume_id == payload.resume_id, GeneratedCv.job_id == payload.job_id
        )
    )
    saved = result.scalars().first()
    if saved:
        saved.content = cv
    else:
        db.add(GeneratedCv(resume_id=payload.resume_id, job_id=payload.job_id, content=cv))
    await db.commit()

    return {"resume_id": payload.resume_id, "job_id": payload.job_id, "cv": cv}
