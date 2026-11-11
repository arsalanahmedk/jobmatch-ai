"""Web UI for JobMatch AI (FastAPI).

Serves the single-page front end in ``web/`` and a ``POST /api/match``
endpoint. The scoring logic lives in exactly one place — the standard
library matcher in :mod:`jobmatch.matcher` — and this module only adapts
it to HTTP. The core matcher stays dependency-free.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from jobmatch.jobs import fetch_jobs
from jobmatch.matcher import analyze

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
EXAMPLES_DIR = BASE_DIR / "examples"

app = FastAPI(
    title="JobMatch AI",
    description="Score how well a resume matches a job description.",
    version="1.1.0",
)


class MatchRequest(BaseModel):
    """Both texts are plain strings; empty is allowed, like the CLI."""

    resume_text: str = Field(default="", description="Full resume text")
    job_text: str = Field(default="", description="Full job description text")
    top_missing: int = Field(
        default=10, ge=1, le=25, description="Missing keywords to return"
    )


@app.get("/", include_in_schema=False)
def index():
    """Serve the single-page front end."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/examples")
def examples():
    """Return the bundled sample resume and job description."""
    resume = (EXAMPLES_DIR / "resume.txt").read_text(encoding="utf-8")
    job = (EXAMPLES_DIR / "job.txt").read_text(encoding="utf-8")
    return {"resume": resume, "job": job}


@app.get("/api/jobs")
def live_jobs(skills: str = "", limit: int = 8):
    """Live jobs matching the given skills, from free job boards.

    ``skills`` is a comma-separated list (e.g. the matched skills from a
    match). Sources are Arbeitnow and RemoteOK — both free, no API key.
    A source that is down just contributes nothing; the endpoint still
    returns whatever the other source found.
    """
    skill_list = [s.strip() for s in skills.split(",") if s.strip()][:8]
    jobs = fetch_jobs(skill_list, limit=limit)
    return {
        "jobs": jobs,
        "skills": skill_list,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/match")
def match(payload: MatchRequest):
    """Score ``resume_text`` against ``job_text``.

    Returns the exact dict :func:`jobmatch.matcher.analyze` produces —
    score, verdict, skill coverage, keyword overlap, matched/missing
    skills, missing keywords, and suggestions.
    """
    return analyze(payload.resume_text, payload.job_text, top_missing=payload.top_missing)
