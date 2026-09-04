"""Generate real CVs via the production pipeline for a spread of fixture pairs,
so we have real material to hand-label for judge calibration.

Usage: python -m evals.generate_cv_samples
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.services.database import AsyncSessionLocal
from app.models.job import Job
from app.models.resume import Resume
from app.services.pipeline import pipeline

OUT = Path(__file__).parent / "cv_samples.jsonl"

SAMPLE_PAIRS = [
    (1, 1),  # strong match — data scientist role
    (1, 2),  # strong match — ML engineer
    (1, 3),  # mismatch — senior LLM production engineer, way too senior
    (1, 4),  # mismatch — unrelated domain, substation design
    (1, 5),  # weak — internship, overqualified
]


async def run() -> None:
    async with AsyncSessionLocal() as db:
        resumes = {r.id: r.content for r in (await db.execute(select(Resume))).scalars()}
        jobs = {j.id: j for j in (await db.execute(select(Job))).scalars()}

    samples = []
    for resume_id, job_id in SAMPLE_PAIRS:
        job = jobs[job_id]
        resume_content = resumes[resume_id]
        print(f"generating CV for resume={resume_id} job={job_id} ({job.title} @ {job.company})...")
        result = await pipeline.ainvoke({
            "resume_content": resume_content,
            "job_title": job.title,
            "company": job.company,
            "experience_required": job.experience_required,
            "job_description": job.description,
            "research": "", "strategy": "", "cv": "", "cover_letter": "", "outreach": "",
        })
        samples.append({
            "resume_id": resume_id,
            "job_id": job_id,
            "resume_content": resume_content,
            "job_description": f"{job.title} at {job.company}\n{job.description}",
            "generated_cv": result["cv"],
        })

    with open(OUT, "w") as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")
    print(f"wrote {len(samples)} samples to {OUT}")


if __name__ == "__main__":
    asyncio.run(run())
