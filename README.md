# JobScout

JobScout collects public job postings, stores them in PostgreSQL with pgvector, matches them against uploaded resumes, and exposes application preparation through the API, chat UI, and MCP.

## What is real

- FastAPI API for jobs, resumes, matching, CV generation, chat, and hunter runs.
- PostgreSQL persistence with an Alembic migration and pgvector support.
- LinkedIn guest search, Indeed search, and Greenhouse/Lever ATS sources.
- Optional Groq, LangSmith, Sentry, Gmail, Google Sheets, and Discord integrations.
- One-shot workers for Fargate: `python -m worker.scrape_once` and `python -m worker.digest_once`.
- Local development scheduler: `python -m worker.main`.
- MCP tools: `search_jobs`, `match_resume`, and `tailor_cv`.
- Pull-request evaluation workflow and main-branch AWS deployment workflow.

## Local setup

1. Create an environment and install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and provide at least `DATABASE_URL` and `API_KEY`.

3. Start PostgreSQL and the API:

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`; the chat UI is at `/` and OpenAPI is at `/docs`.

## Workers

The production image starts with `alembic upgrade head` through `docker-entrypoint.sh`. Fargate scheduled tasks should run the one-shot worker commands. The APScheduler process is intended only for local development.

## Tests and checks

```bash
.venv/bin/python -m compileall -q app worker evals
.venv/bin/pytest -q
```

The LangSmith trajectory check is skipped when `LANGSMITH_API_KEY` is absent.
