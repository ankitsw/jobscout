import asyncio
import json
from groq import AsyncGroq
from pydantic import BaseModel, Field, ValidationError
from duckduckgo_search import DDGS
from app.config import settings

SMALL_MODEL = "llama-3.1-8b-instant"


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


async def _search_company(company_name: str) -> str:
    try:
        results = await asyncio.to_thread(
            lambda: list(DDGS().text(
                f"{company_name} company about size founded tech stack glassdoor",
                max_results=4,
            ))
        )
        if not results:
            return ""
        return "\n\n".join(
            f"{r['title']}\n{r['body'][:300]}" for r in results
        )
    except Exception:
        return ""


async def _extract_profile(company_name: str, raw_results: str) -> CompanyProfile:
    if not raw_results:
        return CompanyProfile(name=company_name)

    client = AsyncGroq(api_key=settings.api_key)
    try:
        resp = await client.chat.completions.create(
            model=SMALL_MODEL,
            max_tokens=400,
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
    except (json.JSONDecodeError, ValidationError, Exception):
        return CompanyProfile(name=company_name)


async def research_company(company_name: str) -> CompanyProfile:
    raw_results = await _search_company(company_name)
    return await _extract_profile(company_name, raw_results)
