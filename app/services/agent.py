import json
import os
import re
import asyncio
import httpx
import numpy as np
from groq import AsyncGroq, RateLimitError
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.prebuilt import create_react_agent
from langsmith import traceable
from sqlalchemy import select, delete
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from ddgs import DDGS
from pydantic import SecretStr
from app.config import settings
from app.services.database import AsyncSessionLocal
from app.models.job import Job
from app.models.resume import Resume
from app.models.chat import ChatMessage
from app.services.pipeline import pipeline
from app.services.sheets import read_sheet, update_job_status
from app.services.scraper import fetch_jobs
from app.services.embeddings import embed
from app.services.company_research import research_company

os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "jobscout"

_groq = AsyncGroq(api_key=settings.api_key)

_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=SecretStr(settings.api_key),
    reasoning_effort="low",
)

_DESTRUCTIVE_KEYWORDS = {"delete", "drop", "wipe", "truncate", "erase"}

_EXP_PATTERNS = [
    r'(\d+)\+\s*years?\s*(?:of\s+)?(?:experience|exp)',
    r'(\d+)[-–]\d+\s*years?\s*(?:of\s+)?(?:experience|exp)',
    r'minimum\s+(\d+)\s*years?\s*(?:of\s+)?(?:experience|exp)',
    r'at\s+least\s+(\d+)\s*years?\s*(?:of\s+)?(?:experience|exp)',
]


def _parse_required_years(description: str) -> int | None:
    text = description.lower()
    for pattern in _EXP_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return int(m.group(1))
    return None


def _parse_user_years(resume_content: str) -> int:
    text = resume_content.lower()
    for pattern in _EXP_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return int(m.group(1))
    return 2


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
async def list_jobs() -> str:
    """List the 10 most recent jobs stored in the database."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Job).order_by(Job.created_at.desc()).limit(10))
        jobs = result.scalars().all()
    return json.dumps([
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "posted_at": j.posted_at,
            "url": j.url,
            "years_required": _parse_required_years(j.description or ""),
        }
        for j in jobs
    ])


@tool
async def match_resume() -> str:
    """Rank the top 5 jobs by semantic similarity against the user's uploaded resume."""
    async with AsyncSessionLocal() as db:
        resume = (await db.execute(select(Resume))).scalars().first()
        jobs = list((await db.execute(select(Job))).scalars().all())
    if not resume:
        return "No resume found. Ask the user to upload one at /resumes/."
    user_years = _parse_user_years(resume.content)
    resume_vec = np.array(embed(resume.content))

    def score(job: Job) -> float:
        job_vec = np.array(embed(f"{job.title} {(job.description or '')[:500]}"))
        s = float(np.dot(resume_vec, job_vec))
        required = _parse_required_years(job.description or "")
        if required is not None and required > user_years + 2:
            s = max(0.0, s - 0.15)
        return s

    scored = await asyncio.gather(*[asyncio.to_thread(score, j) for j in jobs])
    ranked = sorted(zip(jobs, scored), key=lambda x: x[1], reverse=True)[:5]
    return json.dumps([
        {"id": j.id, "title": j.title, "company": j.company, "location": j.location,
         "url": j.url, "score": round(s, 3), "resume_id": resume.id}
        for j, s in ranked
    ])


@tool
async def search_web(query: str) -> str:
    """Search the web for company info, tech stack, culture, or recent news."""
    try:
        results = await asyncio.to_thread(lambda: list(DDGS().text(query, max_results=4)))
        return json.dumps([{"title": r["title"], "body": r["body"][:300]} for r in (results or [])])
    except Exception as e:
        return f"Web search failed: {e}"


@tool
async def prepare_application(job_id: str, resume_id: str) -> str:
    """Generate a tailored CV, cover letter, and LinkedIn outreach for a job.
    Automatically researches the company first."""
    job_id_int = int(job_id or 0)
    resume_id_int = int(resume_id or 0)
    async with AsyncSessionLocal() as db:
        resume = (await db.execute(select(Resume).where(Resume.id == resume_id_int))).scalars().first()
        job = (await db.execute(select(Job).where(Job.id == job_id_int))).scalars().first()
    if not resume:
        return f"Resume {resume_id_int} not found."
    if not job:
        return f"Job {job_id_int} not found."

    company_profile = await research_company(job.company)
    research_text = json.dumps(company_profile.model_dump(), indent=2)
    enriched_description = f"{job.description}\n\n--- Company Research ---\n{research_text}"

    result = await pipeline.ainvoke({
        "resume_content": resume.content,
        "job_title": job.title,
        "company": job.company,
        "experience_required": job.experience_required,
        "job_description": enriched_description,
        "research": "", "strategy": "", "cv": "", "cover_letter": "", "outreach": "",
    })
    return json.dumps({
        "job": f"{job.title} at {job.company}",
        "company_info": company_profile.model_dump(),
        "cv": result["cv"],
        "cover_letter": result["cover_letter"],
        "outreach": result["outreach"],
    })


@tool
async def update_sheet_status(company: str, status: str, notes: str = "") -> str:
    """Update application status in the Google Sheet tracker.
    Status must be one of: Applied, Prepared, Interview, Offer, Rejected."""
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(Job).where(Job.company.ilike(f"%{company}%")))).scalars().first()
    if not job:
        return f"No job found for company '{company}'."
    updated = await update_job_status(job.url, status, "", notes)
    return f"Marked '{job.title}' at {job.company} as '{status}'." if updated else "Job not in sheet yet."


@tool
async def get_tracker() -> str:
    """Read the job application tracker from Google Sheet."""
    records = await read_sheet()
    return json.dumps(records[:20])


@tool
async def search_linkedin(keyword: str, location: str) -> str:
    """Search LinkedIn for new jobs matching a keyword and location, and save them to the database."""
    jobs_data = await fetch_jobs(keyword=keyword, location=location, experience=0)
    async with AsyncSessionLocal() as db:
        saved = 0
        for job_data in jobs_data:
            existing = await db.execute(select(Job).where(Job.url == job_data["url"]))
            if not existing.scalars().first():
                db.add(Job(**job_data))
                saved += 1
        await db.commit()
    return f"Found {len(jobs_data)} jobs for '{keyword}' in '{location}', saved {saved} new."


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

_SYSTEM_JOB_SEARCH = """You are the JobScout Job-Search Agent.
You have access to the jobs database and LinkedIn search. Use your tools to answer every question about available jobs, matching, and experience requirements.
- NEVER answer from your own knowledge — always call a tool first.
- list_jobs → browse what's in the database
- match_resume → rank jobs by resume fit
- search_linkedin → search for new jobs on LinkedIn
Execute first, explain after."""

_SYSTEM_APPLICATION = """You are the JobScout Application-Preparation Agent.
You help users research companies and generate tailored CVs, cover letters, and outreach messages.
- prepare_application automatically researches the company before generating documents.
- Use search_web for additional research if needed.
Execute first, explain after."""

_SYSTEM_TRACKER = """You are the JobScout Tracker Agent.
You manage the Google Sheet application tracker.
- get_tracker → read current status of all applications
- update_sheet_status → mark a job as Applied, Prepared, Interview, Offer, or Rejected
Be concise and confirm every update."""

_SYSTEM_GENERAL = """You are JobScout, an AI-powered job search assistant. Answer the user's general question helpfully and concisely."""

_JOB_SEARCH_AGENT = create_react_agent(
    model=_llm,
    tools=[list_jobs, match_resume, search_linkedin],
    prompt=_SYSTEM_JOB_SEARCH,
)

_APPLICATION_AGENT = create_react_agent(
    model=_llm,
    tools=[search_web, prepare_application, match_resume],
    prompt=_SYSTEM_APPLICATION,
)

_TRACKER_AGENT = create_react_agent(
    model=_llm,
    tools=[update_sheet_status, get_tracker],
    prompt=_SYSTEM_TRACKER,
)

_AGENTS = {
    "job_search": _JOB_SEARCH_AGENT,
    "application": _APPLICATION_AGENT,
    "tracker": _TRACKER_AGENT,
}

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTER_SYSTEM = """You are a request router for a job-search assistant. Classify the user message into exactly one of these intents and reply with ONLY that word — nothing else:

- job_search   → ANY question about jobs, listings, openings, companies hiring, how many jobs, list jobs, find jobs, search jobs, match resume, experience required, job details, LinkedIn search
- application  → preparing a CV, cover letter, researching a company, applying to a specific job
- tracker      → reading or updating the Google Sheet application tracker, checking status
- general      → greetings, chitchat, questions about the assistant itself, non-job topics

When in doubt between job_search and general, always choose job_search.
Reply with one word only."""


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)
async def _groq_create(**kwargs):
    # gpt-oss models spend part of max_tokens on hidden reasoning before the
    # visible answer; "low" keeps that overhead small for these short,
    # single-purpose calls (route labels, summaries) unless overridden.
    kwargs.setdefault("reasoning_effort", "low")
    return await _groq.chat.completions.create(**kwargs)


@traceable(name="router")
async def _route(message: str, history: list[dict]) -> str:
    context = [{"role": "system", "content": _ROUTER_SYSTEM}]
    context.extend(history[-2:])
    context.append({"role": "user", "content": message})
    resp = await _groq_create(
        model="openai/gpt-oss-120b",
        messages=context,
        max_tokens=200,
        temperature=0,
    )
    label = (resp.choices[0].message.content or "general").strip().lower()
    return label if label in _AGENTS or label == "general" else "general"


# ---------------------------------------------------------------------------
# Discord notification
# ---------------------------------------------------------------------------

async def _notify_discord(job_title: str, company: str, job_id: int, cover_letter: str):
    if not settings.discord_webhook_url:
        return
    snippet = cover_letter[:300].replace("\n", " ")
    payload = {
        "embeds": [{
            "title": f"Application prepared: {job_title} @ {company}",
            "description": f"{snippet}…",
            "color": 3447003,
            "footer": {"text": f"job_id={job_id}"},
        }]
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(settings.discord_webhook_url, json=payload, timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Chat memory
# ---------------------------------------------------------------------------

_SUMMARISE_AFTER = 12
_KEEP_EXACT = 5


def _to_lc_messages(history: list[dict]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
        elif msg["role"] == "summary":
            messages.append(SystemMessage(content=f"[Prior conversation summary]: {msg['content']}"))
    return messages


async def _load_history(thread_id: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows: list[ChatMessage] = list((await db.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.created_at)
        )).scalars().all())

    if not rows:
        return []

    raw_turns = [r for r in rows if r.role in ("user", "assistant")]
    if len(raw_turns) > _SUMMARISE_AFTER:
        rows = await _summarise_old_turns(thread_id, rows)

    summary_rows = [r for r in rows if r.role == "summary"]
    raw_rows = [r for r in rows if r.role in ("user", "assistant")]
    recent = raw_rows[-_KEEP_EXACT:]

    messages: list[dict] = []
    if summary_rows:
        messages.append({"role": "user", "content": f"[Conversation summary so far]: {summary_rows[-1].content}"})
        messages.append({"role": "assistant", "content": "Understood. I'll continue from that context."})
    for r in recent:
        messages.append({"role": r.role, "content": r.content})
    return messages


async def _summarise_old_turns(thread_id: str, rows: list) -> list:
    raw_rows = [r for r in rows if r.role in ("user", "assistant")]
    to_summarise = raw_rows[:-_KEEP_EXACT]
    if not to_summarise:
        return rows

    conversation_text = "\n".join(f"{r.role.upper()}: {r.content}" for r in to_summarise)
    summary_resp = await _groq_create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are a concise summariser."},
            {"role": "user", "content": f"Summarise this job-search conversation in under 150 words, preserving key facts (job titles, companies, decisions made):\n\n{conversation_text}"},
        ],
        max_tokens=700,
    )
    summary_text = summary_resp.choices[0].message.content or ""

    ids_to_delete = [r.id for r in to_summarise]
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ChatMessage).where(ChatMessage.id.in_(ids_to_delete)))
        existing_summaries = [r for r in rows if r.role == "summary"]
        if existing_summaries:
            await db.execute(delete(ChatMessage).where(
                ChatMessage.id.in_([r.id for r in existing_summaries])
            ))
        earliest = min(r.created_at for r in to_summarise)
        db.add(ChatMessage(thread_id=thread_id, role="summary", content=summary_text, created_at=earliest))
        await db.commit()

    kept_raw = raw_rows[-_KEEP_EXACT:]
    existing_summaries = [r for r in rows if r.role == "summary"]
    return [r for r in rows if r not in to_summarise and r not in existing_summaries] + kept_raw


async def _save_turn(thread_id: str, user_msg: str, assistant_msg: str):
    async with AsyncSessionLocal() as db:
        db.add(ChatMessage(thread_id=thread_id, role="user", content=user_msg))
        db.add(ChatMessage(thread_id=thread_id, role="assistant", content=assistant_msg))
        await db.commit()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

@traceable(name="jobscout-agent")
async def run_agent(message: str, thread_id: str) -> str:
    if any(word in message.lower().split() for word in _DESTRUCTIVE_KEYWORDS):
        return "I can only read data and update statuses — I cannot delete or reset anything."

    history = await _load_history(thread_id)
    intent = await _route(message, history)

    lc_history = _to_lc_messages(history)
    lc_messages = lc_history + [HumanMessage(content=message)]

    if intent == "general":
        resp = await _llm.ainvoke([SystemMessage(content=_SYSTEM_GENERAL)] + lc_messages)
        response = resp.content or ""
    else:
        agent = _AGENTS[intent]
        result = await agent.ainvoke(
            {"messages": lc_messages},
            config={"recursion_limit": 15},
        )
        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage) and m.content]
        response = ai_msgs[-1].content if ai_msgs else "Done."

    await _save_turn(thread_id, message, str(response))
    return str(response)
