import json
import logging
from groq import AsyncGroq
from pydantic import BaseModel, Field, ValidationError
from tavily import AsyncTavilyClient
from app.config import settings

log = logging.getLogger(__name__)

SMALL_MODEL = "openai/gpt-oss-20b"


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


async def research_company(company_name: str) -> CompanyProfile:
    raw_results = await _search_company(company_name)
    return await _extract_profile(company_name, raw_results)
