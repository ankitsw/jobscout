import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy import select
from app.config import settings
from app.services.database import AsyncSessionLocal
from app.models.job import Job
from app.services.scraper import LinkedInSource, fetch_job_details
from app.services.indeed_scraper import IndeedSource
from app.services.sources.ats import ATSSource
from app.services.sources.base import JobSource
from app.services.embeddings import embed
from app.services.injection_filter import is_likely_injection
from app.services.emailer import send_job_alert_email
from app.services.sheets import append_jobs_to_sheet

# Seconds to wait between LinkedIn per-job description requests. Firing
# these concurrently (the old behavior) got every request 429'd almost
# instantly; a real pause between sequential requests is what actually
# gets descriptions through.
_LINKEDIN_DESCRIPTION_DELAY_SECONDS = 1.0

log = logging.getLogger(__name__)

# Priority order: LinkedIn/Indeed first (richer targeting), ATS last (always
# reachable from a datacenter IP, but coarser). A source erroring or returning
# zero rows must not lose what the others found — see _fetch_source_jobs.
SOURCES: list[JobSource] = [LinkedInSource(), IndeedSource(), ATSSource()]

LOCATIONS = ["New Delhi, India", "Gurugram, India", "Noida, India"]

KEYWORDS = [
    "data scientist",
    "machine learning engineer",
    "AI engineer",
    "NLP engineer",
    "LLM engineer",
    "agentic AI engineer",
    "GenAI engineer",
    "ML platform engineer",
]

SEARCH_PROFILES = [
    {"keyword": keyword, "location": location}
    for keyword in KEYWORDS
    for location in LOCATIONS
]

_TITLE_KEYWORDS = {
    "data scientist", "data science", "machine learning", "ml engineer",
    "ai engineer", "artificial intelligence", "nlp", "natural language",
    "llm", "large language", "agentic", "genai", "generative ai",
    "deep learning", "ml platform", "computer vision", "mlops",
}

_EXCLUDE_TITLE_KEYWORDS = {
    "quality engineer", "quality analyst", "quality analytics",
    "qa engineer", "qa analyst", "test engineer", "sdet",
    "software engineer in test",
}

def _is_relevant(title: str) -> bool:
    t = title.lower()
    if any(kw in t for kw in _EXCLUDE_TITLE_KEYWORDS):
        return False
    return any(kw in t for kw in _TITLE_KEYWORDS)


# Every source (LinkedIn's search results, Greenhouse/Lever's APIs) hands
# back "0" for experience regardless of seniority — none of them actually
# expose it. Pull it from the description text instead, checked in order
# from most to least specific so "3-5 years" doesn't fall through to a
# looser "3 years" match first.
_EXPERIENCE_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\+?\s*years?", re.IGNORECASE),
    re.compile(r"(\d{1,2})\s*\+\s*years?", re.IGNORECASE),
    re.compile(r"(?:minimum|min\.?|at least)\s*(?:of\s*)?(\d{1,2})\s*years?", re.IGNORECASE),
    re.compile(r"(\d{1,2})\s*years?\s+of\s+[a-zA-Z ]{0,30}?experience", re.IGNORECASE),
]


def _extract_experience(text: str) -> str:
    if not text:
        return ""
    match = _EXPERIENCE_PATTERNS[0].search(text)
    if match:
        return f"{match.group(1)}-{match.group(2)} years"
    for pattern in _EXPERIENCE_PATTERNS[1:]:
        match = pattern.search(text)
        if match:
            return f"{match.group(1)}+ years"
    return ""


async def _fetch_source_jobs(source: JobSource, profiles: list[dict]) -> list[dict]:
    """Fetch everything one source has to offer, isolating failures so a
    bad source (or a single failed keyword/location call against it)
    can't lose rows the other sources or other profiles returned."""
    try:
        healthy = await source.health_check()
    except Exception as e:
        log.warning("source health check raised", extra={"source": source.name, "error": repr(e)})
        healthy = False
    if not healthy:
        log.warning("source unhealthy, skipping this run", extra={"source": source.name})
        return []

    if not source.per_profile:
        try:
            return await source.fetch({})
        except Exception as e:
            log.warning("source fetch failed", extra={"source": source.name, "error": repr(e)})
            return []

    results = await asyncio.gather(
        *[source.fetch(p) for p in profiles],
        return_exceptions=True,
    )
    jobs: list[dict] = []
    for profile, result in zip(profiles, results):
        if not isinstance(result, list):
            log.warning(
                "source fetch failed for profile",
                extra={"source": source.name, "keyword": profile["keyword"],
                       "location": profile["location"], "error": repr(result)},
            )
            continue
        jobs.extend(result)
    return jobs


async def scrape_jobs() -> int:
    """Fetch new jobs from every configured source and save them."""
    async with AsyncSessionLocal() as db, httpx.AsyncClient() as linkedin_client:
        new_jobs: list[Job] = []
        alert_jobs: list[dict] = []
        source_counts: dict[str, int] = {}
        for source in SOURCES:
            jobs_data = await _fetch_source_jobs(source, SEARCH_PROFILES)
            source_counts[source.name] = len(jobs_data)
            log.info("source fetch complete", extra={"source": source.name, "count": len(jobs_data)})
            for job_data in jobs_data:
                if not _is_relevant(job_data.get("title", "")):
                    continue
                # Sources return posted_at as "YYYY-MM-DD" (or nothing); the column
                # is TIMESTAMPTZ, so normalise to an aware datetime or None.
                posted_at = job_data.get("posted_at")
                posted_date = None
                if isinstance(posted_at, datetime):
                    posted_date = posted_at if posted_at.tzinfo else posted_at.replace(tzinfo=timezone.utc)
                elif isinstance(posted_at, str) and posted_at.strip():
                    try:
                        posted_date = datetime.strptime(posted_at.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except ValueError:
                        posted_date = None
                if posted_date and datetime.now(timezone.utc) - posted_date > timedelta(days=30):
                    continue
                job_data["posted_at"] = posted_date
                existing = await db.execute(select(Job).where(Job.url == job_data["url"]))
                if existing.scalars().first():
                    continue
                if job_data.get("platform") == "linkedin" and not (job_data.get("description") or "").strip():
                    details = await fetch_job_details(linkedin_client, job_data["url"])
                    job_data["description"] = details.get("description", "")
                    await asyncio.sleep(_LINKEDIN_DESCRIPTION_DELAY_SECONDS)
                job_text = f"{job_data.get('title', '')}\n{job_data.get('description', '')}"
                job_data["experience_required"] = _extract_experience(job_text)
                job_data["embedding"] = embed(job_text)
                try:
                    job_data["flagged"] = await is_likely_injection(job_text)
                except Exception as e:  # noqa: BLE001 - classifier outage must not abort the scrape
                    log.warning(
                        "injection check failed; saving job unflagged",
                        extra={"url": job_data.get("url"), "error": repr(e)},
                    )
                    job_data["flagged"] = False
                job = Job(**job_data)
                db.add(job)
                new_jobs.append(job)
                alert_jobs.append({
                    "job_title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "posted_at": job.posted_at.strftime("%Y-%m-%d") if job.posted_at else "-",
                    "job_url": job.url,
                    "match_score": "-",
                })
        await db.commit()

    if alert_jobs:
        if settings.alert_email and settings.smtp_email and settings.smtp_password:
            try:
                await send_job_alert_email(alert_jobs)
            except Exception:
                log.exception("job alert email failed")
        if settings.google_sheet_id and settings.google_credentials_path:
            try:
                await append_jobs_to_sheet(alert_jobs)
            except Exception:
                log.exception("job sheet append failed")

    log.info("hunter run complete", extra={"source_counts": source_counts, "total_new": len(new_jobs)})
    return len(new_jobs)
