import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from groq import AsyncGroq
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tavily import AsyncTavilyClient

from app.config import settings
from app.models.company import Company
from app.services.ambitionbox import fetch_profile as fetch_ambitionbox_profile
from app.services.ambitionbox import match_salary_for_title

log = logging.getLogger(__name__)

SMALL_MODEL = "openai/gpt-oss-20b"

# Company facts (size, founding, HQ) rarely change; re-fetching every hover
# would burn Tavily/Groq calls for no benefit. Refresh once a row is this old.
_CACHE_MAX_AGE = timedelta(days=30)


class CompanyProfile(BaseModel):
    """Structured company info for the CV pipeline's research field."""
    name: str
    domain: str = ""
    description: str = ""
    size: str = ""
    founded: str = ""
    headquarters: str = ""
    rating: float | None = None
    tech_stack: list[str] = Field(default_factory=list)
    culture_signals: str = ""
    source: str = "web_search"
    classification: str = ""
    ambitionbox_rating: float | None = None
    ambitionbox_reviews_count: int | None = None


class SalaryEstimate(BaseModel):
    matched_title: str = ""
    typical_min_ctc: float | None = None
    typical_max_ctc: float | None = None
    data_points: int = 0


_EXTRACT_PROMPT = """Given these web search results about a company, extract structured info.
Return ONLY valid JSON matching this shape:
{"name": "...", "domain": "...", "description": "2-3 concise sentences summarizing what the company does",
 "size": "...", "founded": "...", "headquarters": "...", "rating": null, "tech_stack": [...],
 "culture_signals": "...", "classification": "..."}

"classification" is the company's type/category, e.g. "IT Services & Consulting", "Product / Software",
"Startup", "Analytics & KPO", "Management Consulting", "Enterprise / MNC" — infer the best fit from the
search results even if not stated explicitly, but do not invent facts for any other field.
If a field isn't findable in the search results, leave it as empty string or null."""


def _normalize(company_name: str) -> str:
    return company_name.strip().lower()


def _profile_from_row(row: Company) -> CompanyProfile:
    return CompanyProfile(
        name=row.name,
        domain=row.domain,
        description=row.description,
        size=row.size,
        founded=row.founded,
        headquarters=row.headquarters,
        rating=row.rating,
        tech_stack=list(row.tech_stack or []),
        culture_signals=row.culture_signals,
        source=row.source,
        classification=row.classification,
        ambitionbox_rating=row.ambitionbox_rating,
        ambitionbox_reviews_count=row.ambitionbox_reviews_count,
    )


def _has_real_data(profile: CompanyProfile) -> bool:
    return bool(
        profile.domain or profile.description or profile.size or profile.founded
        or profile.headquarters or profile.rating is not None or profile.tech_stack
        or profile.culture_signals or profile.classification
        or profile.ambitionbox_rating is not None
    )


async def _search_company(company_name: str) -> str:
    if not settings.tavily_api_key:
        log.warning("no TAVILY_API_KEY configured; skipping company web search")
        return ""
    try:
        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        response = await client.search(
            query=f"{company_name} company about size founded tech stack glassdoor",
            max_results=4,
            search_depth="basic",
        )
        results = response.get("results") or []
        if not results:
            log.warning("company web search returned no results", extra={"company": company_name})
            return ""
        return "\n\n".join(
            f"{r['title']}\n{r['content'][:400]}" for r in results
        )
    except Exception as e:
        log.warning("company web search failed", extra={"company": company_name, "error": repr(e)})
        return ""


async def _extract_profile(company_name: str, raw_results: str) -> CompanyProfile:
    if not raw_results:
        return CompanyProfile(name=company_name)

    client = AsyncGroq(api_key=settings.api_key)
    try:
        resp = await client.chat.completions.create(
            model=SMALL_MODEL,
            max_tokens=700,
            reasoning_effort="low",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _EXTRACT_PROMPT},
                {"role": "user", "content": f"Company: {company_name}\n\nSearch results:\n{raw_results}"},
            ],
        )
        content = resp.choices[0].message.content
        if not content:
            return CompanyProfile(name=company_name)
        parsed = json.loads(content)
        parsed["name"] = company_name
        parsed["source"] = "web_search"
        return CompanyProfile(**parsed)
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        log.warning("company profile extraction failed", extra={"company": company_name, "error": repr(e)})
        return CompanyProfile(name=company_name)


def _predates_ambitionbox_fields(row: Company) -> bool:
    # Rows cached before classification/ambitionbox support existed have
    # none of those fields set. Treat them as stale regardless of age so
    # they pick up the richer data on the next lookup instead of serving
    # an incomplete profile for a full cache cycle.
    return not row.classification and row.ambitionbox_rating is None and not row.ambitionbox_job_profiles


async def research_company(company_name: str, db: AsyncSession) -> CompanyProfile:
    """Look up cached company research first; only hit AmbitionBox/Tavily/Groq
    on a cache miss or when the cached row has gone stale."""
    lookup_key = _normalize(company_name)
    existing = await db.execute(select(Company).where(Company.lookup_key == lookup_key))
    row = existing.scalars().first()

    if row and not _predates_ambitionbox_fields(row) and datetime.now(timezone.utc) - row.updated_at < _CACHE_MAX_AGE:
        return _profile_from_row(row)

    ambitionbox_profile, raw_results = await asyncio.gather(
        fetch_ambitionbox_profile(company_name),
        _search_company(company_name),
    )
    profile = await _extract_profile(company_name, raw_results)

    # AmbitionBox gives real, sourced numbers for rating/classification/HQ;
    # prefer it over the LLM's guess from search snippets whenever it found
    # the company. Description/tech stack/culture still come from Tavily+Groq
    # since AmbitionBox's page doesn't carry those in a usable form.
    job_profiles: list[dict] = []
    if ambitionbox_profile:
        profile.classification = ambitionbox_profile.classification or profile.classification
        profile.ambitionbox_rating = ambitionbox_profile.rating
        profile.ambitionbox_reviews_count = ambitionbox_profile.reviews_count
        profile.headquarters = ambitionbox_profile.headquarters or profile.headquarters
        profile.size = ambitionbox_profile.employee_band or profile.size
        job_profiles = ambitionbox_profile.job_profiles

    if not _has_real_data(profile):
        # Don't overwrite a perfectly good cached row with an empty retry,
        # and don't cache a miss either — let the next lookup try again.
        return _profile_from_row(row) if row else profile

    if row:
        row.domain = profile.domain
        row.description = profile.description
        row.size = profile.size
        row.founded = profile.founded
        row.headquarters = profile.headquarters
        row.rating = profile.rating
        row.tech_stack = profile.tech_stack
        row.culture_signals = profile.culture_signals
        row.source = profile.source
        row.classification = profile.classification
        row.ambitionbox_rating = profile.ambitionbox_rating
        row.ambitionbox_reviews_count = profile.ambitionbox_reviews_count
        if job_profiles:
            row.ambitionbox_job_profiles = job_profiles
    else:
        db.add(Company(
            name=company_name,
            lookup_key=lookup_key,
            domain=profile.domain,
            description=profile.description,
            size=profile.size,
            founded=profile.founded,
            headquarters=profile.headquarters,
            rating=profile.rating,
            tech_stack=profile.tech_stack,
            culture_signals=profile.culture_signals,
            source=profile.source,
            classification=profile.classification,
            ambitionbox_rating=profile.ambitionbox_rating,
            ambitionbox_reviews_count=profile.ambitionbox_reviews_count,
            ambitionbox_job_profiles=job_profiles,
        ))
    await db.commit()
    return profile


async def get_salary_estimate(company_name: str, job_title: str, db: AsyncSession) -> SalaryEstimate:
    """Match a job title against the company's cached AmbitionBox salary
    bands. Triggers a research_company lookup first if the company hasn't
    been researched yet, so the bands are actually available to match."""
    lookup_key = _normalize(company_name)
    existing = await db.execute(select(Company).where(Company.lookup_key == lookup_key))
    row = existing.scalars().first()

    if not row or not row.ambitionbox_job_profiles:
        await research_company(company_name, db)
        existing = await db.execute(select(Company).where(Company.lookup_key == lookup_key))
        row = existing.scalars().first()

    if not row or not row.ambitionbox_job_profiles:
        return SalaryEstimate()

    match = match_salary_for_title(row.ambitionbox_job_profiles, job_title)
    if not match:
        return SalaryEstimate()
    return SalaryEstimate(**match)
