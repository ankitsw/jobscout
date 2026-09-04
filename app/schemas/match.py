from pydantic import BaseModel


class MatchRequest(BaseModel):
    resume_id: int
    job_ids: list[int] | None = None  # None = match against all jobs in DB


class JobMatchOut(BaseModel):
    job_id: int
    title: str
    company: str
    location: str
    url: str
    platform: str
    skill_match: int       # 0-100
    experience_match: int  # 0-100
    role_alignment: int    # 0-100
    seniority_fit: int     # 0-100
    score: int             # weighted total
    summary: str
