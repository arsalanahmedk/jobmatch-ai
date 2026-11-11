# JobMatch AI

A Python tool that scores how well a resume matches a job description —
and tells you exactly what's missing.

Paste in your resume and a job posting, and JobMatch AI reports a match
score (0–100%), the skills you already have, the skills the job wants that
you don't show yet, the keywords you're missing, and concrete suggestions
for closing the gap.

## Why this exists

Most "resume checkers" hide their scoring behind a black box. JobMatch AI
is transparent on purpose:

- **Score = 65% required-skill coverage + 35% keyword overlap.**
- Skills are detected from a curated taxonomy (Python, PyTorch, LLMs,
  Docker, …) with alias and word-boundary aware matching — so "Java" never
  matches "JavaScript".
- Everything runs locally. No API keys, no network calls, no accounts.

## Install

Python 3.10+ and nothing else — the core matcher is standard library only.

```bash
git clone https://github.com/arsalanahmedk/jobmatch-ai.git
cd jobmatch-ai
# No dependencies to install (see requirements.txt)
```

## Run

```bash
# Human-readable report
python -m jobmatch examples/resume.txt examples/job.txt

# Machine-readable result (for scripts / CI)
python -m jobmatch examples/resume.txt examples/job.txt --json

# Show more/fewer missing keywords
python -m jobmatch resume.txt job.txt --top 5
```

Your own files work the same way — save your resume and the job
description as plain `.txt` files and pass their paths.

## Web UI

The same matcher, as a polished single-page app (FastAPI backend, dark
developer theme, animated score gauge). The scoring logic is not
duplicated — the API calls the same `jobmatch.matcher.analyze` the CLI
uses.

```bash
# Install the web dependencies (the core stays stdlib-only)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start the server, then open http://127.0.0.1:8000
uvicorn app:app --reload
```

In the browser you can paste a resume and a job description, load the
bundled sample data with one click, see the animated score ring with
matched vs missing skills, and copy the result or download it as JSON.
The API is also usable directly:

```bash
curl -s -X POST http://127.0.0.1:8000/api/match \
  -H 'Content-Type: application/json' \
  -d '{"resume_text": "...", "job_text": "..."}'
```

## Example output

The bundled example uses a real profile (AI student at PAF-IAST) against a
remote AI/ML Engineer posting:

```
JobMatch AI — Resume vs Job Description
==================================================
Match score: 55 / 100 (Partial match)

Skill coverage: 16 of 25 required skills found (64%)
Keyword overlap: 38% of the job description's terms appear in the resume (30/79)

Matched skills (16):
  Artificial Intelligence, Computer Vision, FastAPI, Git, GitHub, Hugging Face,
  LLMs, Machine Learning, NLP, OpenCV, PyTorch, Python, REST APIs, SQL,
  TensorFlow, Web Scraping

Missing skills (9):
  AWS, CI/CD, Docker, Google Cloud, LangChain, MLOps, Prompt Engineering,
  RAG, Vector Databases

Top missing keywords:
  - features (mentioned 3x in the job description)
  - prompt (mentioned 3x in the job description)
  - cloud (mentioned 2x in the job description)
  - databases (mentioned 2x in the job description)
  - rag (mentioned 2x in the job description)

Suggestions:
  - Add evidence of Docker — a project, bullet point or certification that actually uses it.
  - Add evidence of RAG — a project, bullet point or certification that actually uses it.
  - Add evidence of LangChain — a project, bullet point or certification that actually uses it.
  - Mirror more of the job description's wording: reuse its key terms
    (features, prompt, cloud) in your experience bullets.
```

The 55 isn't a failure — it's a to-do list. The missing skills (Docker,
RAG, LangChain, Prompt Engineering…) are exactly the next things to learn
and show in a project.

## What a recruiter sees

- A candidate who tailors their resume to the role instead of sending the
  same PDF everywhere.
- A working CLI tool, tested, with a clean README — not a notebook demo.
- The sample resume and job description are real, so the output above is
  reproducible in one command.

## Project structure

```
jobmatch-ai/
├── app.py               # FastAPI backend: serves web/ + POST /api/match
├── web/
│   └── index.html       # Single-page front end (score ring, skills, export)
├── jobmatch/
│   ├── __init__.py      # Public API: analyze, extract_skills, extract_keywords
│   ├── __main__.py      # `python -m jobmatch` entry point
│   ├── cli.py           # Argument parsing, human + JSON output
│   ├── matcher.py       # Scoring, keyword extraction, suggestions
│   └── skills.py        # Skill taxonomy (canonical names + aliases)
├── tests/
│   └── test_matcher.py  # 18 unit tests (stdlib unittest)
├── examples/
│   ├── resume.txt       # Sample resume (AI student, PAF-IAST)
│   └── job.txt          # Sample AI/ML Engineer job description
├── README.md
├── requirements.txt     # Stdlib core; FastAPI + Uvicorn for the web UI only
├── .gitignore
└── LICENSE              # MIT
```

## Tests

```bash
python -m unittest discover -s tests -v
```

18 tests, all passing. They cover skill extraction (including aliases and
the Java-vs-JavaScript trap), keyword frequencies, scoring edge cases
(empty resume = 0, identical texts = 100), JSON output, and the CLI itself.

## License

MIT — see `LICENSE`.
