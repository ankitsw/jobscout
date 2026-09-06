# app/routers/resume.py
import io
import pdfplumber
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.rate_limit import limiter
from app.services.database import get_db
from app.models.resume import Resume
from app.schemas.resume import ResumeOut, ResumeRename

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("/", response_model=list[ResumeOut])
async def get_list_of_resumes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).order_by(Resume.created_at.desc()))
    return result.scalars().all()


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.post("/", response_model=ResumeOut)
@limiter.limit("10/minute")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    pdf_bytes = await file.read()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        content = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    if not content.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")
    # Fall back to the uploaded filename (minus extension) so a resume is
    # never stuck with no label just because the user skipped naming it.
    resume_name = name.strip() or (file.filename or "").rsplit(".", 1)[0]
    new_resume = Resume(content=content, name=resume_name)
    db.add(new_resume)
    await db.commit()
    await db.refresh(new_resume)
    return new_resume


@router.patch("/{resume_id}", response_model=ResumeOut)
async def rename_resume(resume_id: int, payload: ResumeRename, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.name = payload.name.strip()
    await db.commit()
    await db.refresh(resume)
    return resume


@router.delete("/{resume_id}")
async def delete_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    await db.delete(resume)
    await db.commit()
    return {"detail": f"Resume with ID: {resume_id} deleted"}
