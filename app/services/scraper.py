import html
import json
import re
import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.services.sources.base import JobSource

_JOB_POSTING_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)

# schema.org JobPosting.employmentType values LinkedIn actually uses, mapped
# to the same job_type vocabulary hunter.py's text-based fallback produces.
_EMPLOYMENT_TYPE_MAP = {
    "FULL_TIME": "full_time",
    "PART_TIME": "part_time",
    "CONTRACTOR": "contract",
    "TEMPORARY": "contract",
    "INTERN": "internship",
}


def _clean_jsonld_description(raw: str) -> str:
    # LinkedIn's JSON-LD description is rich text: HTML tags with entities
    # double-escaped inside the JSON string (e.g. "&lt;strong&gt;"). Unescape
    # once to get real HTML, then strip tags down to plain text.
    unescaped = html.unescape(raw)
    return BeautifulSoup(unescaped, "html.parser").get_text(separator="\n").strip()


# Work type filters
WORK_TYPE = {
    "remote": "2",
    "onsite": "1",
    "hybrid": "3",
}

# Job type filters
JOB_TYPE = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "internship": "I",
}

# Experience level filters
EXPERIENCE_LEVEL = {
    "internship": "1",
    "entry": "2",       # 0-1 years
    "associate": "3",   # 1-3 years
    "mid_senior": "4",  # 3-5 years
    "director": "5",
    "executive": "6",
}


async def fetch_job_details(client: httpx.AsyncClient, job_url: str) -> dict:
    """Fetch a job's own posting page and read its embedded schema.org
    JobPosting JSON-LD. This is the same public page LinkedIn serves for SEO,
    so it doesn't get rate-limited the way the jobs-guest AJAX API does, and
    parsing one JSON blob is more robust than matching a CSS class that can
    change. Also surfaces the hiring company's LinkedIn industry tag as a
    free classification signal.
    """
    if not job_url:
        return {}
    try:
        resp = await client.get(job_url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return {}
        match = _JOB_POSTING_JSONLD_RE.search(resp.text)
        if not match:
            return {}
        data = json.loads(match.group(1))
        employment_type_raw = (data.get("employmentType") or "").split(",")[0].strip().upper()
        return {
            "description": _clean_jsonld_description(data.get("description") or ""),
            "industry": (data.get("industry") or "").strip(),
            "job_type": _EMPLOYMENT_TYPE_MAP.get(employment_type_raw, ""),
        }
    except Exception:
        return {}


async def fetch_jobs(
    keyword: str,
    location: str,
    experience: int,
    work_type: str | None = None,
    job_type: str | None = None,
    experience_level: str | None = None,
    easy_apply: bool = False,
    sort_by_date: bool = False,
    pages: int = 1,
) -> list[dict]:
    keyword_encoded = keyword.replace(" ", "+")
    location_encoded = location.replace(" ", "+")

    filters = ""

    if work_type and work_type in WORK_TYPE:
        filters += f"&f_WT={WORK_TYPE[work_type]}"

    if job_type and job_type in JOB_TYPE:
        filters += f"&f_JT={JOB_TYPE[job_type]}"

    if experience_level:
        codes = [EXPERIENCE_LEVEL[l.strip()] for l in experience_level.split(",") if l.strip() in EXPERIENCE_LEVEL]
        if codes:
            filters += f"&f_E={','.join(codes)}"

    if easy_apply:
        filters += "&f_LF=f_AL"

    if sort_by_date:
        filters += "&sortBy=DD"

    results = []

    for page in range(pages):
        start = page * 10
        url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={keyword_encoded}&location={location_encoded}&start={start}{filters}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("li")

            if not cards:
                break

            for card in cards:
                if not isinstance(card, Tag):
                    continue
                title_el = card.find("h3", class_="base-search-card__title")
                company_el = card.find("h4", class_="base-search-card__subtitle")
                location_el = card.find("span", class_="job-search-card__location")
                url_el = card.find("a", class_="base-card__full-link")
                posted_el = card.find("time", class_="job-search-card__listdate")
                url = str(url_el.get("href") or "").split("?")[0] if isinstance(url_el, Tag) else ""
                posted_at = str(posted_el.get("datetime") or "") if isinstance(posted_el, Tag) else ""

                results.append({
                    "title": title_el.get_text(strip=True) if title_el else "",
                    "company": company_el.get_text(strip=True) if company_el else "",
                    "location": location_el.get_text(strip=True) if location_el else "",
                    "url": url,
                    "posted_at": posted_at,
                    "description": "",
                    # hunter.py fills this in from the description text;
                    # LinkedIn's search results don't expose a real value.
                    "experience_required": "",
                    "platform": "linkedin",
                    "easy_apply": easy_apply,
                })

    # Descriptions aren't fetched here: hitting LinkedIn's per-job endpoint
    # for every listing (most of which are already in the DB from a prior
    # run) blasts it with dozens of concurrent requests and gets rate-limited
    # almost immediately. hunter.py fetches descriptions one at a time,
    # paced, and only for jobs that turn out to be genuinely new.
    return results


class LinkedInSource(JobSource):
    """Thin JobSource wrapper around fetch_jobs — parsing logic unchanged.
    Blocks reliably from datacenter IPs (see hunter.py / ATSSource)."""

    name = "linkedin"

    async def fetch(self, profile: dict) -> list[dict]:
        return await fetch_jobs(
            keyword=profile.get("keyword", ""),
            location=profile.get("location", ""),
            experience=int(profile.get("experience", 0)),
            work_type=profile.get("work_type"),
            job_type=profile.get("job_type"),
            experience_level=profile.get("experience_level"),
            easy_apply=bool(profile.get("easy_apply", False)),
            sort_by_date=True,
            pages=int(profile.get("pages", 1)),
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    "?keywords=engineer&location=India&start=0",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception:
            return False
