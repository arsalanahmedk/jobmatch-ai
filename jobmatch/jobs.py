"""Live job discovery for JobMatch AI.

Fetches fresh job listings from two free, keyless job APIs — Arbeitnow
and RemoteOK — and filters them to the user's matched skills. No API
keys, no accounts, no new dependencies (standard library only).

All network access is best-effort: a source that is down or slow just
yields no jobs instead of failing the request. Results are cached in
memory for 10 minutes per skill set.
"""

import json
import re
import time
import urllib.request
from datetime import datetime, timezone

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
REMOTEOK_URL = "https://remoteok.com/api"
TIMEOUT_SECONDS = 8
CACHE_TTL_SECONDS = 600
MAX_SKILLS = 8

_CACHE = {}

_USER_AGENT = {"User-Agent": "JobMatch-AI/1.1 (job discovery; contact: github.com/arsalanahmedk/jobmatch-ai)"}


def _fetch_json(url):
    """GET a JSON URL, returning the parsed object or None on any failure."""
    request = urllib.request.Request(url, headers=_USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as resp:
            return json.load(resp)
    except Exception:
        return None


def _clean_text(html_or_text):
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html_or_text or "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?:;])", r"\1", text)
    return text


def _skill_hit(skill, haystack):
    """True when a skill appears as a whole word/phrase (case-insensitive).

    Word-boundary aware, so "Java" does not match "JavaScript" and "C++"
    still matches "C++ developer".
    """
    pattern = r"(?<!\w)" + re.escape(skill.lower()) + r"(?!\w)"
    return re.search(pattern, haystack) is not None


def normalize_arbeitnow(raw):
    """Normalize one Arbeitnow job dict, or None when it is unusable."""
    if not isinstance(raw, dict):
        return None
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title or not url:
        return None
    description = _clean_text(raw.get("description"))
    location = (raw.get("location") or "").strip()
    if not location and raw.get("remote"):
        location = "Remote"
    # Arbeitnow's created_at is an epoch int; normalize to an ISO string
    # so sorting and display never mix types.
    posted = raw.get("created_at") or ""
    if isinstance(posted, (int, float)):
        posted = datetime.fromtimestamp(posted, tz=timezone.utc).isoformat()
    else:
        posted = str(posted)
    return {
        "title": title,
        "company": (raw.get("company_name") or "").strip(),
        "location": location,
        "url": url,
        "tags": [str(t) for t in (raw.get("tags") or [])],
        "snippet": description[:220],
        "posted_at": posted,
        "source": "Arbeitnow",
    }


def normalize_remoteok(raw):
    """Normalize one RemoteOK job dict, or None when it is unusable.

    RemoteOK's first list item is a legal notice without a position;
    it is skipped here.
    """
    if not isinstance(raw, dict) or "position" not in raw:
        return None
    title = (raw.get("position") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title or not url:
        return None
    description = _clean_text(raw.get("description"))
    salary = ""
    low = raw.get("salary_min")
    high = raw.get("salary_max")
    if low and high:
        salary = "$%s–$%s" % (f"{int(low):,}", f"{int(high):,}")
    elif low:
        salary = "from $%s" % f"{int(low):,}"
    return {
        "title": title,
        "company": (raw.get("company") or "").strip(),
        "location": (raw.get("location") or "").strip(),
        "url": url,
        "tags": [str(t) for t in (raw.get("tags") or [])],
        "snippet": description[:220],
        "posted_at": str(raw.get("date") or ""),
        "source": "RemoteOK",
        "salary": salary,
    }


def job_skill_hits(job, skills):
    """How many of the skills a job mentions (title, tags, snippet)."""
    haystack = " ".join(
        [
            job.get("title", ""),
            " ".join(job.get("tags", [])),
            job.get("snippet", ""),
        ]
    ).lower()
    return sum(1 for skill in skills if skill and _skill_hit(skill, haystack))


def filter_jobs(jobs, skills, limit=8):
    """Keep jobs matching at least one skill, best matches first.

    Ranked by number of skills hit, then by most recent posting.
    Duplicates (same URL) are removed; at most ``limit`` are returned.
    """
    scored = []
    seen_urls = set()
    for job in jobs:
        url = job.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        hits = job_skill_hits(job, skills)
        if hits > 0:
            scored.append((hits, job.get("posted_at", ""), job))
    scored.sort(key=lambda item: item[1], reverse=True)  # newest first
    scored.sort(key=lambda item: item[0], reverse=True)  # most skills first
    return [job for _, _, job in scored[:limit]]


def _load_source(url, is_arbeitnow):
    """Fetch one source and return its normalized jobs (possibly empty)."""
    data = _fetch_json(url)
    if data is None:
        return []
    if is_arbeitnow:
        raw_list = data.get("data", []) if isinstance(data, dict) else []
        return [job for job in (normalize_arbeitnow(r) for r in raw_list) if job]
    if isinstance(data, list):
        return [job for job in (normalize_remoteok(r) for r in data) if job]
    return []


def fetch_jobs(skills, limit=8):
    """Live jobs matching any of ``skills`` (best matches first).

    Returns a list of normalized job dicts. Returns [] when there are no
    skills, or when both sources are unreachable.
    """
    skills = [s.strip() for s in (skills or []) if s and s.strip()][:MAX_SKILLS]
    if not skills:
        return []
    limit = max(1, min(int(limit or 8), 20))
    key = tuple(sorted(s.lower() for s in skills))
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return list(cached[1][:limit])

    jobs = []
    jobs.extend(_load_source(ARBEITNOW_URL, is_arbeitnow=True))
    jobs.extend(_load_source(REMOTEOK_URL, is_arbeitnow=False))
    matched = filter_jobs(jobs, skills, limit=limit)
    _CACHE[key] = (now, matched)
    return list(matched)


def clear_cache():
    """Clear the in-memory jobs cache (mainly for tests)."""
    _CACHE.clear()
