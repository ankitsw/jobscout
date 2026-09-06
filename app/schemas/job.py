from datetime import datetime
from pydantic import BaseModel, Field

class JobBase(BaseModel):
    title:str
    company:str
    location:str
    description:str
    experience_required:str
    job_type:str = ""
    workplace_type:str = ""
    platform:str
    url:str
    easy_apply:bool = Field(default=False)
    posted_at:datetime | None = None

class JobCreate(JobBase):
    pass

class JobOut(JobBase):
    model_config = {"from_attributes": True}
    id:int
    created_at:datetime
    updated_at:datetime

class JobSearchRequest(BaseModel):
    keyword: str
    locations: list[str] | None = None
    experience: int
    work_type: str
    job_type: str
    experience_level: str
    easy_apply: bool | None = None
    sort_by_date: bool = False
    pages: int = 1
    