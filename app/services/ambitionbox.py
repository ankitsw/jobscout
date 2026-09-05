import json
import logging
import re

import httpx
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


class AmbitionBoxProfile(BaseModel):
    rating: float | None = None
    reviews_count: int | None = None
    classification: str = ""
    headquarters: str = ""
    employee_band: str = ""
    job_profiles: list[dict] = Field(default_factory=list)


def _slugify(company_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower().strip()).strip("-")


def _extract_industry(info_tags: list[dict]) -> str:
    # The industry tag is the one entry in infoTags without a "type" key
    # (headquarters and employee-count entries both carry one).
    for tag in info_tags:
        if "type" not in tag and tag.get("name"):
            return tag["name"]
    return ""


def _extract_headquarters(info_tags: list[dict]) -> str:
    for tag in info_tags:
        if tag.get("type") == "headquarters":
            return tag.get("name", "").removeprefix("HQ - ").strip()
    return ""


async def fetch_profile(company_name: str) -> AmbitionBoxProfile | None:
    """Fetch a company's AmbitionBox overview page and parse its embedded
    Next.js data. Returns None if the company isn't listed, the slug guess
    resolves to an unrelated page, or the request fails for any reason."""
    slug = _slugify(company_name)
    if not slug:
        return None
    url = f"https://www.ambitionbox.com/overview/{slug}-overview"
    try:
        # Short timeout: on some hosting networks AmbitionBox appears to
        # silently drop requests rather than reject them, so a slow failure
        # here would otherwise stall the whole company-research response.
        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            match = _NEXT_DATA_RE.search(resp.text)
            if not match:
                return None
            data = json.loads(match.group(1))
            page_props = data["props"]["pageProps"]

            header = page_props.get("companyHeaderData") or {}
            name_on_page = (header.get("companyName") or "").lower()
            # Loose sanity check: the slug guess can land on an unrelated
            # company page. Require at least one shared word.
            if not any(word in name_on_page for word in company_name.lower().split() if len(word) > 2):
                return None

            info_tags = header.get("infoTags") or []
            job_profiles = (
                (page_props.get("salariesList") or {}).get("designations", {}).get("jobProfiles") or []
            )

            return AmbitionBoxProfile(
                rating=header.get("rating"),
                reviews_count=header.get("reviewsCount"),
                classification=_extract_industry(info_tags),
                headquarters=_extract_headquarters(info_tags),
                employee_band=next(
                    (i.get("label", "") for i in header.get("info", []) if i.get("type") == "TotalEmployeesIndia"),
                    "",
                ),
                job_profiles=job_profiles,
            )
    except Exception as e:
        log.warning("ambitionbox fetch failed", extra={"company": company_name, "error": repr(e)})
        return None


def _normalize_title(title: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", title.lower()).split() if len(w) > 2}


def match_salary_for_title(job_profiles: list[dict], job_title: str) -> dict | None:
    """Find the AmbitionBox salary band whose job profile name best overlaps
    the given job title. Returns None below a minimal overlap threshold
    rather than guessing at a mismatch."""
    target_words = _normalize_title(job_title)
    if not target_words or not job_profiles:
        return None

    best_score = 0
    best_profile = None
    for profile in job_profiles:
        name = profile.get("jobProfileName", "")
        profile_words = _normalize_title(name)
        if not profile_words:
            continue
        overlap = target_words & profile_words
        score = len(overlap) / max(len(profile_words), 1)
        if score > best_score:
            best_score = score
            best_profile = profile

    if not best_profile or best_score < 0.5:
        return None

    try:
        return {
            "matched_title": best_profile.get("jobProfileName", ""),
            "typical_min_ctc": float(best_profile["typicalMinCtc"]),
            "typical_max_ctc": float(best_profile["typicalMaxCtc"]),
            "data_points": int(best_profile.get("dataPoints") or 0),
        }
    except (KeyError, TypeError, ValueError):
        return None
