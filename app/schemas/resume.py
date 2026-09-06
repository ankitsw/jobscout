from datetime import datetime
from pydantic import BaseModel, Field

class ResumeBase(BaseModel):
    content:str

class ResumeCreate(ResumeBase):
    pass

class ResumeOut(ResumeBase):
    id: int
    name: str = ""
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class ResumeRename(BaseModel):
    name: str = Field(min_length=1, max_length=200)