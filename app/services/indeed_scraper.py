from __future__ import annotations

import logging
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.services.sources.base import JobSource

log = logging.getLogger(__name__)


class IndeedSource(JobSource):
    name = "indeed"
    per_profile = True

    async def fetch(self, profile: dict) -> list[dict]:
        keyword = profile.get("keyword", "")
        location = profile.get("location", "")
        url = f"https://in.indeed.com/jobs?q={quote_plus(keyword)}&l={quote_plus(location)}"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                return []
        except httpx.HTTPError as exc:
            log.warning("indeed request failed", extra={"error": repr(exc)})
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[dict] = []
        for card in soup.select("div.job_seen_beacon"):
            if not isinstance(card, Tag):
                continue
            title = card.select_one("h2.jobTitle")
            company = card.select_one("span.companyName")
            location_el = card.select_one("div.companyLocation")
            link = card.select_one("h2.jobTitle a")
            if not isinstance(link, Tag):
                continue
            href = str(link.get("href") or "")
            if not href:
                continue
            if href.startswith("/"):
                href = f"https://in.indeed.com{href}"
            jobs.append({
                "title": title.get_text(strip=True) if isinstance(title, Tag) else "",
                "company": company.get_text(strip=True) if isinstance(company, Tag) else "",
                "location": location_el.get_text(strip=True) if isinstance(location_el, Tag) else location,
                "url": href.split("?")[0],
                "posted_at": "",
                "description": "",
                "experience_required": "",
                "platform": self.name,
                "easy_apply": bool(profile.get("easy_apply", False)),
            })
        return jobs

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://in.indeed.com/", headers={"User-Agent": "Mozilla/5.0"})
            return response.status_code < 500
        except httpx.HTTPError:
            return False
