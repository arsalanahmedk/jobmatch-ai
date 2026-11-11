"""Command-line interface for JobMatch AI."""

import argparse
import json
import sys

from .matcher import analyze


def build_parser():
    parser = argparse.ArgumentParser(
        prog="jobmatch",
        description="Score how well a resume matches a job description.",
    )
    parser.add_argument("resume", help="Path to the resume text file")
    parser.add_argument("job", help="Path to the job description text file")
    parser.add_argument(
        "--json", action="store_true", help="Print the result as JSON"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="How many missing keywords to show (default 10)",
    )
    return parser


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def format_report(result):
    """Render the analysis as a human-readable report."""
    lines = []
    lines.append("JobMatch AI — Resume vs Job Description")
    lines.append("=" * 50)
    lines.append(f"Match score: {result['score']} / 100 ({result['verdict']})")
    lines.append("")
    lines.append(
        f"Skill coverage: {len(result['matched_skills'])} of "
        f"{len(result['required_skills'])} required skills found "
        f"({result['skill_coverage'] * 100:.0f}%)"
    )
    lines.append(
        f"Keyword overlap: {result['keyword_overlap'] * 100:.0f}% of the job "
        f"description's terms appear in the resume "
        f"({result['matched_keywords']}/{result['total_keywords']})"
    )
    lines.append("")
    lines.append(f"Matched skills ({len(result['matched_skills'])}):")
    lines.append("  " + (", ".join(result["matched_skills"]) or "— none —"))
    lines.append("")
    lines.append(f"Missing skills ({len(result['missing_skills'])}):")
    lines.append("  " + (", ".join(result["missing_skills"]) or "— none —"))
    lines.append("")
    lines.append("Top missing keywords:")
    if result["missing_keywords"]:
        for item in result["missing_keywords"]:
            lines.append(
                f"  - {item['keyword']} "
                f"(mentioned {item['mentions']}x in the job description)"
            )
    else:
        lines.append("  — none —")
    lines.append("")
    lines.append("Suggestions:")
    for suggestion in result["suggestions"]:
        lines.append(f"  - {suggestion}")
    return "\n".join(lines)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        resume_text = _read(args.resume)
        jd_text = _read(args.job)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"jobmatch: error: {exc}", file=sys.stderr)
        return 2
    result = analyze(resume_text, jd_text, top_missing=args.top)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
