# JobScout

An agentic job-search assistant: scrapes postings from multiple platforms,
ranks them against a resume with vector similarity, and uses an LLM agent
to research companies and draft tailored CVs, cover letters, and outreach.
FastAPI backend + React dashboard, deployed on Render.

See [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) for architecture details.

## Local setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in at least DATABASE_URL and API_KEY (Groq)
docker compose up --build
```

App runs at `http://localhost:8000`; API docs at `/docs`. Leave
`SITE_ACCESS_KEY` unset locally — the login gate only activates when it's
set.

## Deploy to Render (free tier)

1. Push to GitHub, then in the Render dashboard: **New > Blueprint**,
   point it at the repo. `render.yaml` provisions a Postgres 16 database
   and a Docker web service.
2. Fill in secrets when prompted — `API_KEY` (Groq) is the only one
   required. `TAVILY_API_KEY` enables company research and web search;
   without it those return empty instead of failing. Set
   `SITE_ACCESS_KEY` + `SESSION_SECRET` to gate the site behind a
   password (generate `SESSION_SECRET` with
   `python -c "import secrets; print(secrets.token_hex(32))"`).
3. Deploy — `docker-entrypoint.sh` runs `alembic upgrade head` (creates
   the `vector` extension too) before starting `uvicorn`.

Push to the tracked branch to redeploy.

**Free-tier tradeoffs:** the web service spins down after 15 minutes idle
(30-60s cold start on the next request), and the free Postgres database
is deleted 30 days after creation unless upgraded. For indefinite free
persistence, point `DATABASE_URL` at Neon or Supabase instead and drop
the `databases:` block from `render.yaml`.

## Scheduled scraping (via GitHub Actions)

Render's Cron Jobs aren't free; [`.github/workflows/scrape.yml`](.github/workflows/scrape.yml)
runs `python -m worker.scrape_once` twice daily (06:00/18:00 UTC) instead.

Setup:
1. In the Render Postgres dashboard, copy the **External** connection
   string (not internal — GitHub's runners aren't on Render's network),
   and add `0.0.0.0/0` to the database's Access Control.
2. In GitHub: **Settings > Secrets and variables > Actions**, add
   `DATABASE_URL` (external string) and `API_KEY` (same Groq key).
3. Trigger a manual run from the Actions tab to confirm it works.

GitHub disables scheduled workflows after 60 days of repo inactivity —
push a commit or re-enable it from the Actions tab if that happens.

## Tests

```bash
.venv/bin/python -m compileall -q app worker evals
.venv/bin/pytest -q
```
