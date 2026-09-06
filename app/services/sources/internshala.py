"""Internshala as a JobSource.

India's dominant internship platform. Its listing pages are plain
server-rendered HTML (no SPA framework, no bot challenge encountered in
testing) with the full card content - title, company, location, stipend,
duration, and a real description snippet - all present in the initial
response, so unlike LinkedIn/Hirist this needs no second per-job request.
"""
import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.services.sources.base import JobSource

BASE_URL = "https://internshala.com/internships/{slug}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

# A few categories rather than every possible keyword: Internshala's own
# relevance sort surfaces adjacent roles anyway, and hunter.py's title
# filter discards anything that doesn't actually match.
CATEGORY_SLUGS = [
    "data-science-internship",
    "machine-learning-internship",
    "artificial-intelligence-internship",
]


def _normalize_card(card: Tag) -> dict | None:
    link = card.select_one("a.job-title-href")
    company = card.select_one("p.company-name")
    if not link or not company:
        return None

    href = card.get("data-href") or link.get("href") or ""
    url = f"https://internshala.com{href}" if href.startswith("/") else str(href)

    location_el = card.select_one(".locations span")
    stipend_el = card.select_one(".stipend")
    about_el = card.select_one(".about_job .text")

    description = about_el.get_text("\n", strip=True) if about_el else ""
    if stipend_el:
        description = f"Stipend: {stipend_el.get_text(strip=True)}\n\n{description}"

    return {
        "title": link.get_text(strip=True),
        "company": company.get_text(strip=True),
        "location": location_el.get_text(strip=True) if location_el else "Remote",
        "url": url,
        "posted_at": "",
        "description": description,
        "experience_required": "",
        "job_type": "internship" if card.get("employment_type") == "internship" else "",
        "platform": "internshala",
        "easy_apply": False,
    }


class InternshalaSource(JobSource):
    name = "internshala"
    per_profile = False

    async def fetch(self, profile: dict) -> list[dict]:
        jobs: list[dict] = []
        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=20) as client:
            for slug in CATEGORY_SLUGS:
                try:
                    resp = await client.get(BASE_URL.format(slug=slug))
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for card in soup.select("div.individual_internship"):
                        normalized = _normalize_card(card)
                        if normalized:
                            jobs.append(normalized)
                except Exception:
                    continue
        return jobs

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=10) as client:
                resp = await client.get(BASE_URL.format(slug=CATEGORY_SLUGS[0]))
                return resp.status_code == 200
        except Exception:
            return False
