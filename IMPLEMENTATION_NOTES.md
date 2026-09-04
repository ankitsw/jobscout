# JobScout Implementation Notes

This document records the changes made during the implementation and the reason behind each step.

## 1. Inspected the Existing Project

Reviewed the FastAPI entrypoint, configuration, database layer, routers, job sources, worker-related services, evaluation files, Docker files, and dependency list.

### Reason

The requested work crossed several boundaries. Reading the existing contracts first was necessary to avoid creating duplicate APIs or incompatible worker behavior.

## 2. Aligned the Job Source Interface

Updated the common `JobSource.fetch()` contract so sources receive one profile dictionary.

Updated LinkedIn and ATS sources to follow that contract. Updated the hunter pipeline to pass profile dictionaries instead of separate keyword and location arguments.

### Reason

The base source abstraction already described a profile-based interface, but the concrete sources and hunter were using different signatures. This caused static-analysis errors and would cause runtime argument errors.

## 3. Added the Missing Indeed Source

Created `app/services/indeed_scraper.py` with:

- Profile-based Indeed search.
- HTML result parsing.
- Normalized job dictionaries.
- Health checking.
- Network failure handling.

### Reason

`hunter.py` imported `IndeedSource`, but the module did not exist. Adding a compatible source restored the intended multi-source scraping pipeline while keeping failures isolated.

## 4. Added the Embedding Service

Created `app/services/embeddings.py` with:

- Sentence Transformer loading when available.
- Normalized embeddings from `all-MiniLM-L6-v2`.
- A deterministic hash-based fallback when the model cannot load.

### Reason

`hunter.py` and the agent imported `embed`, but no implementation existed. The fallback keeps local development and tests from failing solely because a large model is unavailable.

## 5. Fixed the Injection Filter API Call

Replaced the unsupported `AsyncGroq.predict()` call with `AsyncGroq.chat.completions.create()` and handled an empty response safely.

### Reason

The installed Groq SDK exposes chat completions, not `predict()`. The old call would fail at runtime whenever injection filtering ran.

## 6. Restored Hunter Notifications

Updated `scrape_jobs()` to optionally:

- Send new-job email alerts.
- Append new jobs to Google Sheets.

Added `send_digest()` as a wrapper around the existing email alert implementation.

### Reason

The scraping pipeline had notification services available, but the current hunter flow did not call them. Integration calls are gated by configured credentials so scraping still works when those services are intentionally disabled.

## 7. Added Fargate One-Shot Workers

Created:

- `worker/scrape_once.py`
- `worker/digest_once.py`

Both configure logging, perform one operation, and exit with an appropriate async entrypoint.

### Reason

Fargate scheduled tasks need finite processes that complete one job and stop. Keeping these separate from the persistent scheduler makes deployment behavior predictable.

## 8. Added the Local APScheduler Worker

Created `worker/main.py` and `worker/__init__.py`.

The worker:

- Runs one scrape immediately.
- Schedules future scrapes using `HUNTER_INTERVAL_MINUTES`.
- Keeps the process alive for local development.

### Reason

A persistent scheduler is useful during local development, but it should not be used as the Fargate execution model. The scheduler was also corrected to create an active recurring job rather than a paused job.

## 9. Added Structured Logging

Created `app/logging_config.py` with:

- JSON log output.
- UTC timestamps.
- Log levels and logger names.
- Request ID correlation.
- Selected structured fields such as source, path, status, and error.

### Reason

JSON logs are easier to query in container platforms. Request IDs let one API request be followed across middleware and application logs.

## 10. Added Rate Limiting

Created `app/rate_limit.py` using SlowAPI with a default request limit.

Added a stricter limit to the manual hunter endpoint.

### Reason

Scraping and AI-backed routes can be expensive. A shared limiter provides a baseline guard, while the hunter route receives an explicitly tighter limit because it triggers external work and database writes.

## 11. Added Sentry and Request-ID Middleware

Updated `app/main.py` to:

- Initialize Sentry only when a DSN is configured.
- Install the SlowAPI limiter.
- Add the rate-limit exception handler.
- Generate or propagate `X-Request-ID`.
- Return the request ID in the response header.

### Reason

Optional initialization prevents local startup failures when observability credentials are absent. Middleware centralizes request correlation and rate-limit behavior for all routes.

## 12. Added Migration-First Docker Startup

Created `docker-entrypoint.sh`:

```sh
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

Updated both Dockerfiles to make the script executable and use it as the container command.

### Reason

The application should not serve traffic against an outdated schema. Running migrations before Uvicorn provides deterministic startup behavior for deployed containers.

## 13. Added the Hunter Router

Created `app/routers/hunter.py` with a rate-limited `POST /hunter/run` endpoint.

Registered it in `app/main.py`.

### Reason

The scraping pipeline needed an explicit API control surface for manual operations, health checks, and future operational tooling.

## 14. Added the Chat UI

Created `app/static/index.html` and registered `GET /` in `app/main.py`.

The page provides:

- A responsive JobScout interface.
- A prompt textarea.
- A chat submission button.
- A response area connected to `/agent/chat`.

### Reason

The requested application needed a usable first screen rather than only backend endpoints. The UI uses the existing agent route instead of duplicating assistant logic in the browser.

## 15. Added MCP Tools

Created `mcp_server.py` with:

- `search_jobs`
- `match_resume`
- `tailor_cv`

The implementation was adapted to the installed MCP v2 SDK using `MCPServer` and the stdio runner.

### Reason

The first MCP import attempt used the older `FastMCP` API and failed with the installed `mcp==2.1.1`. Inspecting the installed SDK showed that MCP v2 uses `MCPServer`, so the entrypoint was updated to the version actually present in the project.

## 16. Added LangSmith Trajectory Evaluation

Created `evals/trajectory.py` and `evals/__init__.py`.

The evaluator:

- Checks required run types in recent traces.
- Uses the configured LangSmith project.
- Skips cleanly when no LangSmith API key is configured.
- Returns a failing exit code when structural checks fail.

### Reason

Trace evaluation should inspect real traces when credentials exist, but local tests and pull requests without secrets should not fail with an import or credential error.

## 17. Added CI Evaluation Workflow

Created `.github/workflows/evals.yml` to run on every pull request.

It installs dependencies, runs evaluation tests, and executes the trajectory check.

### Reason

Retrieval and adversarial evaluation regressions should be visible before merging changes.

## 18. Added Deployment Workflow

Created `.github/workflows/deploy.yml` to:

1. Check out the repository.
2. Install dependencies and Ruff.
3. Run linting, compilation, and tests.
4. Configure AWS through OIDC.
5. Log in to ECR.
6. Build and push the Docker image.
7. Update the App Runner service.

### Reason

The workflow makes the deployment sequence explicit and ensures quality checks run before publishing an image or updating App Runner.

## 19. Added Documentation

Created `README.md` describing:

- What the application currently implements.
- Local setup.
- Docker startup.
- Worker commands.
- MCP tools.
- Tests and evaluation behavior.

### Reason

Documentation was written after implementation so it describes the actual code and commands rather than planned functionality.

## 20. Validation Performed

The following checks passed:

- Pylance/editor diagnostics for the changed application files.
- Python compilation for `app`, `worker`, `evals`, and `mcp_server.py`.
- FastAPI application import using `.venv/bin/python`.
- MCP server import using the installed MCP v2 SDK.
- Full test suite: `10 passed`.
- Docker Compose configuration validation.
- Presence of the migration entrypoint, README, worker files, workflows, and static UI.

One route-listing verification initially assumed every FastAPI route object had a `.path` attribute. Included routers do not always expose that attribute directly, so the check was rerun using a safe attribute lookup and passed.

## Result

The requested worker, operations, deployment, MCP, evaluation, hunter, and UI surfaces are now present and wired into the existing application. External integrations such as Groq, SMTP, Google Sheets, Sentry, LangSmith, AWS, and LinkedIn/Indeed still require their corresponding credentials and service availability to perform live operations.
