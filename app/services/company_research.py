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


_EXTRACT_PROMPT = """Given these web search results about a company, extract structured info.
Return ONLY valid JSON matching this shape:
{"name": "...", "domain": "...", "description": "one sentence", "size": "...", "founded": "...",
 "headquarters": "...", "rating": null, "tech_stack": [...], "culture_signals": "..."}

If a field isn't findable in the search results, leave it as empty string or null. Do not guess or invent information."""


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
    )


def _has_real_data(profile: CompanyProfile) -> bool:
    return bool(
        profile.domain or profile.description or profile.size or profile.founded
        or profile.headquarters or profile.rating is not None or profile.tech_stack
        or profile.culture_signals
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


async def research_company(company_name: str, db: AsyncSession) -> CompanyProfile:
    """Look up cached company research first; only hit Tavily/Groq on a
    cache miss or when the cached row has gone stale."""
    lookup_key = _normalize(company_name)
    existing = await db.execute(select(Company).where(Company.lookup_key == lookup_key))
    row = existing.scalars().first()

    if row and datetime.now(timezone.utc) - row.updated_at < _CACHE_MAX_AGE:
        return _profile_from_row(row)

    raw_results = await _search_company(company_name)
    profile = await _extract_profile(company_name, raw_results)

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
        ))
    await db.commit()
    return profile
