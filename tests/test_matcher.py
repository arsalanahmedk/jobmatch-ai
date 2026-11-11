"""Unit tests for JobMatch AI (standard library unittest)."""

import contextlib
import json
import os
import sys
import tempfile
import unittest
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jobmatch import analyze, extract_keywords, extract_skills
from jobmatch.cli import format_report, main


class TestSkillExtraction(unittest.TestCase):
    def test_case_insensitive_and_aliases(self):
        skills = extract_skills("I used PyTorch, HuggingFace and LLM APIs.")
        self.assertIn("PyTorch", skills)
        self.assertIn("Hugging Face", skills)
        self.assertIn("LLMs", skills)

    def test_java_not_matched_by_javascript(self):
        skills = extract_skills("Built a web app with JavaScript and React.")
        self.assertIn("JavaScript", skills)
        self.assertNotIn("Java", skills)

    def test_multiword_skill(self):
        skills = extract_skills("Experienced in machine learning and deep learning.")
        self.assertIn("Machine Learning", skills)
        self.assertIn("Deep Learning", skills)

    def test_hyphenated_skill(self):
        skills = extract_skills("Built classifiers with scikit-learn and pandas.")
        self.assertIn("scikit-learn", skills)
        self.assertIn("Pandas", skills)


class TestKeywordExtraction(unittest.TestCase):
    def test_stopwords_dropped(self):
        keywords = extract_keywords(
            "The candidate will work with the team and build models."
        )
        self.assertNotIn("the", keywords)
        self.assertNotIn("and", keywords)
        self.assertIn("models", keywords)

    def test_frequencies_counted(self):
        keywords = extract_keywords("Python python Python and docker.")
        self.assertEqual(keywords["python"], 3)
        self.assertEqual(keywords["docker"], 1)


class TestAnalyze(unittest.TestCase):
    JD = (
        "We need a Python developer with PyTorch and SQL. Experience with "
        "Docker and AWS is a plus. Strong machine learning background required."
    )
    RESUME = (
        "Python developer. Built ML models with PyTorch and scikit-learn. "
        "Worked with SQL databases and Docker containers."
    )

    def test_matched_and_missing_skills(self):
        result = analyze(self.RESUME, self.JD)
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("PyTorch", result["matched_skills"])
        self.assertIn("Docker", result["matched_skills"])
        self.assertIn("AWS", result["missing_skills"])
        self.assertIn("Machine Learning", result["matched_skills"])

    def test_score_between_zero_and_100(self):
        result = analyze(self.RESUME, self.JD)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_identical_texts_score_100(self):
        result = analyze(self.JD, self.JD)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["verdict"], "Strong match")

    def test_empty_resume_scores_zero(self):
        result = analyze("", self.JD)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["verdict"], "Weak match")

    def test_empty_job_description(self):
        result = analyze(self.RESUME, "")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["required_skills"], [])

    def test_json_serializable(self):
        result = analyze(self.RESUME, self.JD)
        parsed = json.loads(json.dumps(result))
        self.assertEqual(parsed["score"], result["score"])

    def test_suggestions_exist(self):
        result = analyze(self.RESUME, self.JD)
        self.assertTrue(result["suggestions"])
        self.assertTrue(
            any("AWS" in s for s in result["suggestions"]),
            "suggestions should name the missing skill",
        )

    def test_missing_keywords_ranked_by_frequency(self):
        jd = "Docker docker docker. Kubernetes kubernetes. Python."
        result = analyze("Python developer.", jd, top_missing=2)
        self.assertEqual(result["missing_keywords"][0]["keyword"], "docker")
        self.assertEqual(result["missing_keywords"][0]["mentions"], 3)


class TestCli(unittest.TestCase):
    def _run_cli(self, args):
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(args)
        self.assertEqual(code, 0)
        return buf.getvalue()

    def test_cli_human_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            resume = os.path.join(tmp, "resume.txt")
            job = os.path.join(tmp, "job.txt")
            with open(resume, "w", encoding="utf-8") as f:
                f.write("Python developer with PyTorch.")
            with open(job, "w", encoding="utf-8") as f:
                f.write("Looking for a Python developer with PyTorch and Docker.")
            output = self._run_cli([resume, job])
        self.assertIn("Match score", output)
        self.assertIn("Docker", output)

    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            resume = os.path.join(tmp, "resume.txt")
            job = os.path.join(tmp, "job.txt")
            with open(resume, "w", encoding="utf-8") as f:
                f.write("Python developer with PyTorch.")
            with open(job, "w", encoding="utf-8") as f:
                f.write("Looking for a Python developer with PyTorch and Docker.")
            output = self._run_cli([resume, job, "--json"])
        parsed = json.loads(output)
        self.assertIn("score", parsed)
        self.assertIn("matched_skills", parsed)
        self.assertIn("missing_skills", parsed)

    def test_cli_missing_file_returns_2(self):
        with contextlib.redirect_stderr(StringIO()):
            code = main(["nope-resume.txt", "nope-job.txt"])
        self.assertEqual(code, 2)

    def test_format_report_contains_sections(self):
        result = analyze("Python developer.", "Python developer with Docker.")
        report = format_report(result)
        for section in (
            "Match score",
            "Matched skills",
            "Missing skills",
            "Suggestions",
        ):
            self.assertIn(section, report)


if __name__ == "__main__":
    unittest.main()
