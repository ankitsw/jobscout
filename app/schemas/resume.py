from datetime import datetime
from pydantic import BaseModel, Field

class ResumeBase(BaseModel):
    content:str

class ResumeCreate(ResumeBase):
    pass

class ResumeOut(ResumeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}