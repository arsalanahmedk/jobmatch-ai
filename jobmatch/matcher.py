"""Core matching logic for JobMatch AI (standard library only).

The score is deliberately explainable: 65% required-skill coverage and 35%
keyword overlap between the resume and the job description. Nothing is
hidden behind a black box, so a candidate can see exactly what to fix.
"""

import re
from collections import Counter

from .skills import SKILLS

STOPWORDS = frozenset(
    """
    a an the and or but if then else when at by for with about against between
    into through during before after above below to from up down in out on off
    over under again further once here there all any both each few more most
    other some such no nor not only own same so than too very can will just
    should now is am are was were be been being have has had having do does
    did doing would could shall may might must of as it its this that these
    those i you he she we they them his her their our your my me him us who
    whom which what how why where experience years year work team teams role
    job company candidate candidates looking join strong ability based skills
    skill knowledge understanding background including includes required
    requirements preferred plus etc within across per via using use used build
    building develop developing create creating working help helps end
    responsible responsibilities duties passion passionate excellent good
    great looking forward apply application hiring hire hired
    """.split()
)

_WEIGHT_SKILLS = 0.65
_WEIGHT_KEYWORDS = 0.35


def normalize_text(text):
    """Lowercase text and normalise separators so matching is consistent."""
    text = text.lower()
    for ch in "-_/":
        text = text.replace(ch, " ")
    return re.sub(r"\s+", " ", text).strip()


def _skill_regex(alias):
    alias = normalize_text(alias)
    # Look-behind blocks matches inside longer words ("torch" in "pytorch")
    # and inside dotted names ("js" in "node.js"). The look-ahead must NOT
    # block a trailing full stop, so "pandas." still counts as Pandas.
    return re.compile(r"(?<![a-z0-9+#.])" + re.escape(alias) + r"(?![a-z0-9+#])")


def extract_skills(text):
    """Return the set of canonical skill names found in *text*."""
    norm = normalize_text(text)
    found = set()
    for canonical, aliases in SKILLS.items():
        for alias in aliases:
            if _skill_regex(alias).search(norm):
                found.add(canonical)
                break
    return found


def _tokens(text):
    norm = normalize_text(text)
    raw = re.findall(r"[a-z][a-z0-9+#.]*", norm)
    # Strip sentence-ending full stops ("models." -> "models").
    tokens = [t.rstrip(".") for t in raw]
    return [t for t in tokens if len(t) >= 3 and t not in STOPWORDS]


def extract_keywords(text):
    """Return a Counter of meaningful terms in *text*."""
    return Counter(_tokens(text))


def _verdict(score):
    if score >= 80:
        return "Strong match"
    if score >= 60:
        return "Good match"
    if score >= 40:
        return "Partial match"
    return "Weak match"


def analyze(resume_text, jd_text, top_missing=10):
    """Score how well *resume_text* matches *jd_text*.

    Returns a JSON-serialisable dict with the score (0-100), matched and
    missing skills, keyword overlap, and concrete suggestions.
    """
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)
    resume_tokens = set(_tokens(resume_text))
    jd_keywords = extract_keywords(jd_text)

    matched_skills = sorted(jd_skills & resume_skills)
    missing_skills = sorted(jd_skills - resume_skills)
    skill_coverage = (len(matched_skills) / len(jd_skills)) if jd_skills else 0.0

    unique_jd = set(jd_keywords)
    matched_keywords = sorted(t for t in unique_jd if t in resume_tokens)
    keyword_overlap = (len(matched_keywords) / len(unique_jd)) if unique_jd else 0.0

    missing_kw = sorted(
        ((kw, jd_keywords[kw]) for kw in unique_jd if kw not in resume_tokens),
        key=lambda item: (-item[1], item[0]),
    )[:top_missing]

    if not jd_skills and not jd_keywords:
        return {
            "score": 0,
            "verdict": "Weak match",
            "skill_coverage": 0.0,
            "keyword_overlap": 0.0,
            "required_skills": [],
            "matched_skills": [],
            "missing_skills": [],
            "matched_keywords": 0,
            "total_keywords": 0,
            "missing_keywords": [],
            "suggestions": [
                "The job description looks empty — check the file and try again."
            ],
        }

    score = round(100 * (_WEIGHT_SKILLS * skill_coverage + _WEIGHT_KEYWORDS * keyword_overlap))

    suggestions = []
    for skill in missing_skills:
        suggestions.append(
            f"Add evidence of {skill} — a project, bullet point or "
            "certification that actually uses it."
        )
    if keyword_overlap < 0.5 and jd_keywords:
        top_terms = ", ".join(kw for kw, _ in missing_kw[:3])
        suggestions.append(
            "Mirror more of the job description's wording: reuse its key "
            f"terms ({top_terms}) in your experience bullets."
        )
    if score >= 80:
        suggestions.append(
            "Strong fit — tailor your top two bullets to the hiring team's "
            "exact stack to stand out."
        )
    elif score < 40:
        suggestions.append(
            "Tailor this resume for the role: lead with the projects that "
            "use the required stack."
        )
    if not missing_skills and jd_skills:
        suggestions.append(
            "All required skills are present — quantify impact (users, "
            "speed, accuracy) to make them land."
        )

    return {
        "score": score,
        "verdict": _verdict(score),
        "skill_coverage": round(skill_coverage, 3),
        "keyword_overlap": round(keyword_overlap, 3),
        "required_skills": sorted(jd_skills),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_keywords": len(matched_keywords),
        "total_keywords": len(unique_jd),
        "missing_keywords": [
            {"keyword": kw, "mentions": count} for kw, count in missing_kw
        ],
        "suggestions": suggestions,
    }
