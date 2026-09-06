"""Hirist (hirist.tech) as a JobSource.

Unlike LinkedIn's search results page, Hirist's listing API
(gladiator.hirist.tech) is a plain, public, unauthenticated JSON endpoint -
no rate-limiting observed in testing. It's India-focused and tech-recruiting
specific, so results skew toward the same data/ML/AI roles this app targets.

The list endpoint doesn't include the job description; that requires a
second call per job to the detail endpoint (see fetch_description below,
called from hunter.py's paced enrichment step, the same pattern already
used for LinkedIn - firing all of these concurrently is exactly what got
LinkedIn's per-job endpoint rate-limited before).
"""
import html
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.services.sources.base import JobSource

SEARCH_URL = "https://gladiator.hirist.tech/job/search"
DETAIL_URL = "https://gladiator.hirist.tech/job/detail"

# Hirist's search has no useful location filter (India-focused already), so
# unlike LinkedIn there's nothing to gain from crossing this with a location
# list - just search by keyword directly.
KEYWORDS = [
    "data scientist",
    "machine learning engineer",
    "ai engineer",
    "nlp engineer",
    "genai engineer",
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
_JOB_ID_RE = re.compile(r"-(\d+)$")


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    return BeautifulSoup(html.unescape(raw), "html.parser").get_text(separator="\n").strip()


def _normalize_job(item: dict) -> dict:
    locations = ", ".join(loc.get("name", "") for loc in (item.get("locations") or []) if loc.get("name"))
    min_exp, max_exp = item.get("min"), item.get("max")
    experience_required = f"{min_exp}-{max_exp} years" if min_exp is not None and max_exp is not None else ""

    posted_at = ""
    created_ms = item.get("createdTimeMs") or item.get("createdTime")
    if created_ms:
        posted_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    company = (item.get("companyData") or {}).get("companyName") or item.get("creatorDomainName", "")

    return {
        "title": (item.get("title") or "").strip(),
        "company": company.strip(),
        "location": locations or "India",
        "url": item.get("jobDetailUrl", ""),
        "posted_at": posted_at,
        # Left empty deliberately: hunter.py only fetches the full detail-page
        # description (via fetch_description below) when this is empty. A
        # placeholder here would silently suppress that fetch.
        "description": "",
        "experience_required": experience_required,
        "platform": "hirist",
        "easy_apply": False,
    }


async def fetch_description(client: httpx.AsyncClient, job_url: str) -> str:
    """Fetch a job's full description from Hirist's detail API. The job id
    is the trailing number in its URL (.../role-slug-<id>)."""
    match = _JOB_ID_RE.search(job_url)
    if not match:
        return ""
    try:
        resp = await client.get(DETAIL_URL, params={"jobcode": match.group(1)}, headers=_HEADERS)
        if resp.status_code != 200:
            return ""
        intro = (resp.json().get("data") or {}).get("introText", "")
        return _strip_html(intro)
    except Exception:
        return ""


class HiristSource(JobSource):
    name = "hirist"
    per_profile = False

    async def fetch(self, profile: dict) -> list[dict]:
        jobs: list[dict] = []
        async with httpx.AsyncClient(headers=_HEADERS, timeout=20) as client:
            for keyword in KEYWORDS:
                try:
                    resp = await client.get(
                        SEARCH_URL,
                        params={"query": keyword, "page": 0, "posting": 0, "industry": "", "size": 20},
                    )
                    if resp.status_code != 200:
                        continue
                    items = resp.json().get("data") or []
                    jobs.extend(_normalize_job(item) for item in items)
                except Exception:
                    continue
        return jobs

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as client:
                resp = await client.get(
                    SEARCH_URL,
                    params={"query": "engineer", "page": 0, "posting": 0, "industry": "", "size": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False
