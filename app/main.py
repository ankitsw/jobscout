import uuid
from typing import cast

import sentry_sdk
from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.logging_config import configure_logging, request_id_context
from app.rate_limit import limiter
from app.services.auth import require_access
from app.services.database import get_db
from app.routers import auth, job, resume
from app.routers import match
from app.routers import cv
from app.routers import agent
from app.routers import hunter

configure_logging()
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)

app = FastAPI(title="JobScout", version="0.1.0")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


async def rate_limit_handler(request: Request, exc: Exception):
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_context.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response

# auth.router must stay ungated - it's the only way to log in.
app.include_router(auth.router)

_gate = [Depends(require_access)]
app.include_router(job.router, dependencies=_gate)
app.include_router(resume.router, dependencies=_gate)
app.include_router(match.router, dependencies=_gate)
app.include_router(cv.router, dependencies=_gate)
app.include_router(agent.router, dependencies=_gate)
app.include_router(hunter.router, dependencies=_gate)

# The React app (frontend/) is built to frontend/dist by the Dockerfile's
# Node stage. Vite's hashed JS/CSS bundles live under dist/assets; index.html
# is served for both client-side routes since react-router (BrowserRouter)
# handles the actual routing once the page loads.
app.mount(
    "/assets",
    StaticFiles(directory="frontend/dist/assets", check_dir=False),
    name="assets",
)


@app.get("/", include_in_schema=False)
@app.get("/jobs-all", include_in_schema=False)
async def spa():
    return FileResponse("frontend/dist/index.html")

@app.get("/health")
def health():
    return {"status": "ok", "service": "jobscout"}


@app.get("/db-health")
async def db_health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}
