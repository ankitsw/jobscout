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
from app.services.sources.hirist import HiristSource
from app.services.sources.hirist import fetch_description as fetch_hirist_description
from app.services.sources.internshala import InternshalaSource
from app.services.sources.base import JobSource
from app.services.embeddings import embed
from app.services.injection_filter import is_likely_injection
from app.services.emailer import send_job_alert_email
from app.services.sheets import append_jobs_to_sheet

# Seconds to wait between per-job description requests on sources that need
# a second call to get the full text. Firing these concurrently (the old
# LinkedIn behavior) got every request 429'd almost instantly; a real pause
# between sequential requests is what actually gets descriptions through.
_DESCRIPTION_FETCHERS = {
    "linkedin": (fetch_job_details, 1.0),
    "hirist": (fetch_hirist_description, 0.5),
}

log = logging.getLogger(__name__)

# Priority order: LinkedIn/Indeed first (richer targeting), ATS/Hirist/
# Internshala last (always reachable from a datacenter IP, but coarser). A
# source erroring or returning zero rows must not lose what the others
# found — see _fetch_source_jobs.
SOURCES: list[JobSource] = [
    LinkedInSource(), IndeedSource(), ATSSource(), HiristSource(), InternshalaSource(),
]

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


# Greenhouse/Lever expose no employment-type field at all, and LinkedIn's own
# JobPosting JSON-LD is missing it on some listings — this text fallback
# covers both. Checked most-specific-first so "internship" doesn't get
# swallowed by a looser pattern.
_JOB_TYPE_PATTERNS = [
    (re.compile(r"\bintern(?:ship)?\b", re.IGNORECASE), "internship"),
    (re.compile(r"\bpart[\s-]?time\b", re.IGNORECASE), "part_time"),
    (re.compile(r"\b(?:contract|contractor|temporary|fixed[\s-]?term)\b", re.IGNORECASE), "contract"),
    (re.compile(r"\bfull[\s-]?time\b", re.IGNORECASE), "full_time"),
]


def _extract_job_type(text: str) -> str:
    if not text:
        return ""
    for pattern, label in _JOB_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return ""


# None of the sources expose a real work-location field - LinkedIn's search
# cards just give a city (e.g. "Gurugram, Haryana, India"), never the word
# "remote" itself, so a "remote only" filter that checked location alone
# always matched zero jobs. This mirrors _extract_job_type: hybrid is
# checked first so a "hybrid, partly remote" posting isn't misread as fully
# remote.
_WORKPLACE_TYPE_PATTERNS = [
    (re.compile(r"\bhybrid\b", re.IGNORECASE), "hybrid"),
    (re.compile(r"\b(?:remote|work[\s-]?from[\s-]?home|wfh|telecommute)\b", re.IGNORECASE), "remote"),
    (re.compile(r"\bon[\s-]?site\b|\bin[\s-]?office\b|\bwork from office\b", re.IGNORECASE), "onsite"),
]


def _extract_workplace_type(text: str) -> str:
    if not text:
        return ""
    for pattern, label in _WORKPLACE_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return ""


def parse_posted_at(raw) -> datetime | None:
    """Sources return posted_at as "YYYY-MM-DD" (or nothing, or already a
    datetime); the column is TIMESTAMPTZ, so normalise to an aware datetime
    or None rather than passing a bare string through to asyncpg."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


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
    async with AsyncSessionLocal() as db, httpx.AsyncClient() as description_client:
        new_jobs: list[Job] = []
        alert_jobs: list[dict] = []
        source_counts: dict[str, int] = {}
        # The same job can legitimately show up twice within one run - e.g.
        # LinkedIn's own keyword list overlaps enough that one posting
        # matches two different searches. The per-job "does this URL exist"
        # check below only sees committed/flushed rows, not another pending
        # add() from earlier in this same loop, so without this it would
        # queue the same URL twice and crash the whole run on the unique
        # constraint when the second one flushes.
        seen_urls_this_run: set[str] = set()
        for source in SOURCES:
            jobs_data = await _fetch_source_jobs(source, SEARCH_PROFILES)
            source_counts[source.name] = len(jobs_data)
            log.info("source fetch complete", extra={"source": source.name, "count": len(jobs_data)})
            for job_data in jobs_data:
                if not _is_relevant(job_data.get("title", "")):
                    continue
                url = job_data.get("url", "")
                if not url or url in seen_urls_this_run:
                    continue
                posted_date = parse_posted_at(job_data.get("posted_at"))
                if posted_date and datetime.now(timezone.utc) - posted_date > timedelta(days=30):
                    continue
                job_data["posted_at"] = posted_date
                existing = await db.execute(select(Job).where(Job.url == url))
                if existing.scalars().first():
                    continue
                seen_urls_this_run.add(url)
                job_type_hint = ""
                workplace_type_hint = ""
                fetcher = _DESCRIPTION_FETCHERS.get(job_data.get("platform", ""))
                if fetcher and not (job_data.get("description") or "").strip():
                    fetch_fn, delay_seconds = fetcher
                    result = await fetch_fn(description_client, job_data["url"])
                    if isinstance(result, dict):
                        job_data["description"] = result.get("description", "")
                        job_type_hint = result.get("job_type", "")
                        workplace_type_hint = result.get("workplace_type", "")
                    else:
                        job_data["description"] = result or ""
                    await asyncio.sleep(delay_seconds)
                job_text = f"{job_data.get('title', '')}\n{job_data.get('location', '')}\n{job_data.get('description', '')}"
                # Some sources (Hirist's exp range, Internshala's employment_type
                # attribute) already give a real value - don't clobber it with a
                # text-regex guess.
                if not (job_data.get("experience_required") or "").strip():
                    job_data["experience_required"] = _extract_experience(job_text)
                job_data["job_type"] = job_data.get("job_type") or job_type_hint or _extract_job_type(job_text)
                job_data["workplace_type"] = (
                    job_data.get("workplace_type") or workplace_type_hint or _extract_workplace_type(job_text)
                )
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
