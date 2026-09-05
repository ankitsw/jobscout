from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.database import get_db
from app.models.job import Job
from app.schemas.job import JobCreate, JobOut
from app.services.company_research import CompanyProfile, research_company

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"]
)

@router.get("/", response_model=list[JobOut])
async def get_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job))
    jobs = result.scalars().all()
    return jobs

@router.get("/company-research", response_model=CompanyProfile)
async def get_company_research(name: str):
    return await research_company(name)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/", response_model=JobOut)
async def create_job(job: JobCreate, db: AsyncSession = Depends(get_db)):
    new_job = Job(**job.model_dump())
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    return new_job

@router.delete("/{job_id}", response_model=dict)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()
    return {"message": "Job deleted successfully"}

