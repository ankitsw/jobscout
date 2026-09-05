"""Public ATS job boards (Greenhouse, Lever) as a JobSource.

These are JSON APIs intended for public consumption (company career pages
embed them client-side) and don't block datacenter IPs the way LinkedIn
and Indeed do. Board/company lists come from Settings so new targets
don't need a code change.
"""
import html
import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.services.sources.base import JobSource

log = logging.getLogger(__name__)

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{company}?mode=json"

_REQUEST_TIMEOUT = 20


def _parse_tokens(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _strip_html(raw: str) -> str:
    """Greenhouse's `content` field is HTML, itself HTML-entity-escaped
    (e.g. "&lt;div&gt;"). Unescape first or BeautifulSoup sees literal
    "<div>" text instead of a tag to strip."""
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    return BeautifulSoup(unescaped, "html.parser").get_text(separator="\n").strip()


def _normalize_greenhouse_job(job: dict, board: str) -> dict:
    location = (job.get("location") or {}).get("name", "").strip()
    posted_at = (job.get("updated_at") or "")[:10]
    return {
        "title": (job.get("title") or "").strip(),
        "company": board,
        "location": location,
        "url": job.get("absolute_url", ""),
        "posted_at": posted_at,
        "description": _strip_html(job.get("content", "")),
        # hunter.py fills this in from the description text; neither
        # Greenhouse nor Lever expose a real experience field.
        "experience_required": "",
        "platform": "ats_greenhouse",
        "easy_apply": False,
    }


def _normalize_lever_job(job: dict, company: str) -> dict:
    categories = job.get("categories") or {}
    location = (categories.get("location") or "").strip()
    description = job.get("descriptionPlain") or _strip_html(job.get("description", ""))
    posted_ms = job.get("createdAt")
    posted_at = ""
    if posted_ms:
        posted_at = datetime.fromtimestamp(posted_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "title": (job.get("text") or "").strip(),
        "company": company,
        "location": location,
        "url": job.get("hostedUrl", ""),
        "posted_at": posted_at,
        "description": description.strip(),
        "experience_required": "",
        "platform": "ats_lever",
        "easy_apply": False,
    }


async def _fetch_greenhouse_board(client: httpx.AsyncClient, board: str) -> list[dict]:
    resp = await client.get(GREENHOUSE_URL.format(board=board), timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    return [_normalize_greenhouse_job(j, board) for j in jobs]


async def _fetch_lever_company(client: httpx.AsyncClient, company: str) -> list[dict]:
    resp = await client.get(LEVER_URL.format(company=company), timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    postings = resp.json()
    return [_normalize_lever_job(j, company) for j in postings]


class ATSSource(JobSource):
    name = "ats"
    per_profile = False

    def __init__(self, greenhouse_boards: list[str] | None = None, lever_companies: list[str] | None = None):
        self.greenhouse_boards = (
            greenhouse_boards if greenhouse_boards is not None else _parse_tokens(settings.ats_greenhouse_boards)
        )
        self.lever_companies = (
            lever_companies if lever_companies is not None else _parse_tokens(settings.ats_lever_companies)
        )

    async def fetch(self, profile: dict) -> list[dict]:
        jobs: list[dict] = []
        async with httpx.AsyncClient() as client:
            for board in self.greenhouse_boards:
                try:
                    jobs.extend(await _fetch_greenhouse_board(client, board))
                except Exception as e:
                    log.warning("greenhouse board fetch failed", extra={"board": board, "error": repr(e)})
            for company in self.lever_companies:
                try:
                    jobs.extend(await _fetch_lever_company(client, company))
                except Exception as e:
                    log.warning("lever company fetch failed", extra={"company": company, "error": repr(e)})
        return jobs

    async def health_check(self) -> bool:
        target = None
        if self.greenhouse_boards:
            target = GREENHOUSE_URL.format(board=self.greenhouse_boards[0])
        elif self.lever_companies:
            target = LEVER_URL.format(company=self.lever_companies[0])
        if not target:
            return False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(target, timeout=10)
                return resp.status_code == 200
        except Exception:
            return False
