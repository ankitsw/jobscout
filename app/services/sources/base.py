from abc import ABC, abstractmethod

class JobSource(ABC):
    """Common interface for anything that produces job postings for the
    hunter pipeline. fetch() must return dicts matching the fields
    hunter.py builds Job(**job_data) from: title, company, location, url,
    posted_at (YYYY-MM-DD or ""), description (plain text, no HTML),
    experience_required, platform, easy_apply.
    """
    
    name: str
    per_profile: bool = True 
    
    @abstractmethod
    async def fetch(self, profile: dict) -> list[dict]:
        "Return normalized job dicts for one search profile."
        
    @abstractmethod
    async def health_check(self) -> bool:
        "Return True if the source is healthy and can be used, False otherwise."