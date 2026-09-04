from fastapi import APIRouter, Request

from app.rate_limit import limiter
from app.services.hunter import scrape_jobs

router = APIRouter(prefix="/hunter", tags=["hunter"])


@router.post("/run")
@limiter.limit("2/minute")
async def run_hunter(request: Request):
    count = await scrape_jobs()
    return {"new_jobs": count}