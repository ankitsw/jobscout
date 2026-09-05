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
- Render blueprint (`render.yaml`) for a free Docker + managed Postgres deploy, plus a free GitHub Actions cron for scheduled scraping.

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

## Deploy to Render (free)

This repo includes a [render.yaml](render.yaml) blueprint that provisions a managed Postgres instance and a Docker web service, both on Render's free plan.

1. Push this repo to GitHub (or your own remote).
2. In the Render dashboard, choose **New > Blueprint** and point it at the repo. Render reads `render.yaml` and provisions:
   - `jobscout-db` — a managed Postgres 16 database (free plan).
   - `jobscout-api` — a Docker web service built from `DockerFile`, wired to `jobscout-db` via `DATABASE_URL` (free plan).
3. When prompted for the secret env vars (`API_KEY` is the only one required; `SMTP_EMAIL`, `SMTP_PASSWORD`, `ALERT_EMAIL`, `LANGSMITH_API_KEY`, `GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_PATH`, `DISCORD_WEBHOOK_URL`, and `SENTRY_DSN` are optional), fill in whichever integrations you're using and leave the rest blank.
4. Deploy. On boot, `docker-entrypoint.sh` runs `alembic upgrade head` (which also creates the `vector` extension) and then starts `uvicorn` on the port Render assigns.
5. Once live, the chat UI is at the service's root URL and the API docs are at `/docs`.

To redeploy after code changes, push to the branch Render is tracking — it rebuilds and restarts the service automatically.

**Two free-tier tradeoffs to know about:**

- Render's free web services spin down after 15 minutes of no traffic and take 30-60 seconds to wake back up on the next request. Fine for a portfolio project, but the first hit after idle time will be slow.
- Render's free Postgres databases are deleted 30 days after creation unless upgraded to a paid plan. For a portfolio demo that's often fine (recreate it from the blueprint when needed), but if you want the data to persist indefinitely for free, consider pointing `DATABASE_URL` at a free-forever external Postgres instead (Neon and Supabase both offer a free tier with pgvector support and no expiry) and dropping the `databases:` block from `render.yaml`.

## Scheduled scraping (free, via GitHub Actions)

Render Cron Jobs aren't covered by the free tier (they're billed per second, even if cheap), so scraping is scheduled with a GitHub Actions workflow instead — [`.github/workflows/scrape.yml`](.github/workflows/scrape.yml) — which is free for this use (public repos get unlimited free minutes; private repos get 2,000 free minutes/month, far more than two ~1-minute runs a day use).

It runs `python -m worker.scrape_once` twice a day, at 06:00 and 18:00 UTC (`0 6,18 * * *`). To change the times, edit the `cron` line in that file.

Setup:

1. In your Render Postgres dashboard for `jobscout-db`, find the **External Connection String** (not the internal one used by the web service — GitHub's runners aren't on Render's private network).
2. Still in the database's settings, add `0.0.0.0/0` to **Access Control** so connections from GitHub Actions' non-static IPs are allowed.
3. In the GitHub repo, go to **Settings > Secrets and variables > Actions** and add:
   - `DATABASE_URL` — the external connection string from step 1.
   - `API_KEY` — same Groq key used on Render.
   - `SMTP_EMAIL`, `SMTP_PASSWORD`, `ALERT_EMAIL` — optional, only needed if you want per-job alert emails from the scrape run.
4. Trigger a manual run from the Actions tab (**scrape > Run workflow**) to confirm it connects and scrapes before waiting for the schedule.

Note that GitHub disables a scheduled workflow automatically if the repo has no activity for 60 days — push a commit or re-enable it from the Actions tab if that happens. The daily email digest (`worker/digest_once.py`) isn't scheduled by default; add a second job to the same workflow file if you want it.

## Workers

The production image starts with `alembic upgrade head` through `docker-entrypoint.sh`. Fargate scheduled tasks should run the one-shot worker commands. The APScheduler process is intended only for local development.

## Tests and checks

```bash
.venv/bin/python -m compileall -q app worker evals
.venv/bin/pytest -q
```

The LangSmith trajectory check is skipped when `LANGSMITH_API_KEY` is absent.
