"""Unit tests for the live jobs feature (standard library unittest).

No test hits the network: source fetching is mocked, and only the
pure normalization / filtering / caching logic is exercised.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jobmatch import jobs


class TestCleanText(unittest.TestCase):
    def test_decodes_html_entities(self):
        self.assertEqual(
            jobs._clean_text("A&nbsp;B &amp; C"), "A B & C"
        )

    def test_fixes_mojibake_em_dash_and_nbsp(self):
        # UTF-8 em dash and NBSP decoded as Latin-1 by the feed.
        self.assertEqual(
            jobs._clean_text("ML Inference Engineer â\x80\x94 Terminal-Bench"),
            "ML Inference Engineer — Terminal-Bench",
        )
        self.assertEqual(
            jobs._clean_text("searching for anÂ\xa0AI/ML Engineer!"),
            "searching for an AI/ML Engineer!",
        )

    def test_strips_raw_urls_and_empty_parens(self):
        cleaned = jobs._clean_text(
            "Data ( https://addepto.com/ai-consulting/ ) and engineering"
        )
        self.assertNotIn("http", cleaned)
        self.assertNotIn("()", cleaned)
        self.assertEqual(cleaned, "Data and engineering")

    def test_truncates_at_word_boundary_with_ellipsis(self):
        long_text = ("lorem ipsum dolor sit amet " * 20).strip()
        cleaned = jobs._clean_text(long_text, limit=60)
        self.assertTrue(cleaned.endswith("…"))
        self.assertLessEqual(len(cleaned), 61)
        # The last word before the ellipsis is a whole word, never cut.
        self.assertIn(cleaned[:-1].rstrip().split()[-1],
                      {"lorem", "ipsum", "dolor", "sit", "amet"})
        self.assertNotIn("…", cleaned[:-1])

    def test_short_text_is_unchanged(self):
        self.assertEqual(jobs._clean_text("Build APIs with Python."), "Build APIs with Python.")


class TestNormalizeArbeitnow(unittest.TestCase):
    def test_basic_job(self):
        raw = {
            "title": "Python Developer",
            "company_name": "Acme",
            "location": "Berlin",
            "url": "https://www.arbeitnow.com/jobs/1",
            "tags": ["Python", "Django"],
            "description": "<p>Build APIs with <b>Python</b>.</p>",
            "created_at": "2026-11-12T08:00:00.000000Z",
        }
        job = jobs.normalize_arbeitnow(raw)
        self.assertEqual(job["title"], "Python Developer")
        self.assertEqual(job["company"], "Acme")
        self.assertEqual(job["source"], "Arbeitnow")
        self.assertEqual(job["tags"], ["Python", "Django"])
        self.assertEqual(job["snippet"], "Build APIs with Python.")
        self.assertNotIn("<p>", job["snippet"])

    def test_missing_title_or_url_is_dropped(self):
        self.assertIsNone(jobs.normalize_arbeitnow({"url": "https://x.example"}))
        self.assertIsNone(jobs.normalize_arbeitnow({"title": "Dev"}))

    def test_remote_without_location(self):
        job = jobs.normalize_arbeitnow(
            {"title": "Dev", "url": "https://x.example", "remote": True}
        )
        self.assertEqual(job["location"], "Remote")

    def test_epoch_created_at_becomes_iso_string(self):
        job = jobs.normalize_arbeitnow(
            {
                "title": "Dev",
                "url": "https://x.example",
                "created_at": 1794422400,
            }
        )
        self.assertIsInstance(job["posted_at"], str)
        self.assertTrue(job["posted_at"].startswith("2026-11-"))


class TestNormalizeRemoteok(unittest.TestCase):
    def test_basic_job(self):
        raw = {
            "position": "Frontend Engineer",
            "company": "Beta",
            "location": "Remote",
            "url": "https://remoteok.com/remote-jobs/1",
            "tags": ["React", "TypeScript"],
            "description": "Ship UI with React.",
            "date": "2026-11-11T10:00:00+00:00",
            "salary_min": 60000,
            "salary_max": 90000,
        }
        job = jobs.normalize_remoteok(raw)
        self.assertEqual(job["title"], "Frontend Engineer")
        self.assertEqual(job["source"], "RemoteOK")
        self.assertEqual(job["salary"], "$60,000–$90,000")

    def test_legal_notice_item_is_skipped(self):
        # RemoteOK's first list item has no "position" key.
        self.assertIsNone(jobs.normalize_remoteok({"legal": "notice"}))

    def test_messy_feed_text_is_cleaned(self):
        # Mojibake title, &nbsp; entity, inline URL and a long excerpt.
        raw = {
            "position": "ML Inference Engineer â\x80\x94 Terminal-Bench",
            "company": "Toptal",
            "location": "Remote",
            "url": "https://remoteok.com/remote-jobs/5",
            "tags": ["Python"],
            "description": (
                "We are searching for anÂ\xa0AI/ML Engineer! "
                "See https://example.com/role for the full spec. "
                + "Great role with real impact. " * 12
            ),
            "date": "2026-11-12T00:00:00+00:00",
        }
        job = jobs.normalize_remoteok(raw)
        self.assertEqual(job["title"], "ML Inference Engineer — Terminal-Bench")
        self.assertNotIn("Â", job["snippet"])
        self.assertNotIn("&nbsp;", job["snippet"])
        self.assertNotIn("http", job["snippet"])
        self.assertTrue(job["snippet"].endswith("…"))
        self.assertLessEqual(len(job["snippet"]), 181)


class TestSkillMatching(unittest.TestCase):
    def test_java_does_not_match_javascript(self):
        job = {
            "title": "JavaScript Developer",
            "tags": ["JavaScript", "React"],
            "snippet": "Build web apps with JavaScript.",
        }
        self.assertEqual(jobs.job_skill_hits(job, ["Java"]), 0)
        self.assertEqual(jobs.job_skill_hits(job, ["JavaScript"]), 1)

    def test_cpp_matches(self):
        job = {"title": "C++ Engineer", "tags": [], "snippet": "Modern C++."}
        self.assertEqual(jobs.job_skill_hits(job, ["C++"]), 1)

    def test_case_insensitive(self):
        job = {"title": "PYTHON Developer", "tags": [], "snippet": ""}
        self.assertEqual(jobs.job_skill_hits(job, ["Python"]), 1)

    def test_empty_skills_never_match(self):
        job = {"title": "Python Developer", "tags": [], "snippet": ""}
        self.assertEqual(jobs.job_skill_hits(job, []), 0)


class TestFilterJobs(unittest.TestCase):
    def _job(self, url, title, tags=None, posted="2026-11-12T00:00:00Z"):
        return {
            "title": title,
            "company": "Co",
            "location": "Remote",
            "url": url,
            "tags": tags or [],
            "snippet": title,
            "posted_at": posted,
            "source": "Test",
        }

    def test_ranked_by_skill_hits(self):
        one_hit = self._job("https://x/1", "Python Developer")
        two_hit = self._job("https://x/2", "Python and Docker Engineer")
        result = jobs.filter_jobs(
            [one_hit, two_hit], ["Python", "Docker"], limit=5
        )
        self.assertEqual([j["url"] for j in result], ["https://x/2", "https://x/1"])

    def test_no_match_is_dropped(self):
        job = self._job("https://x/1", "Go Developer")
        self.assertEqual(jobs.filter_jobs([job], ["Python"]), [])

    def test_duplicates_removed(self):
        a = self._job("https://x/1", "Python Developer")
        b = self._job("https://x/1", "Python Developer")
        self.assertEqual(len(jobs.filter_jobs([a, b], ["Python"])), 1)

    def test_limit_respected(self):
        found = [self._job("https://x/%d" % i, "Python Dev") for i in range(5)]
        self.assertEqual(len(jobs.filter_jobs(found, ["Python"], limit=2)), 2)


class TestFetchJobs(unittest.TestCase):
    def setUp(self):
        jobs.clear_cache()

    def tearDown(self):
        jobs.clear_cache()

    def test_empty_skills_returns_empty_without_network(self):
        with mock.patch.object(jobs, "_fetch_json") as fetch:
            self.assertEqual(jobs.fetch_jobs([]), [])
            fetch.assert_not_called()

    def test_failed_sources_return_empty(self):
        with mock.patch.object(jobs, "_fetch_json", return_value=None):
            self.assertEqual(jobs.fetch_jobs(["Python"]), [])

    def test_mocked_sources_filtered_and_cached(self):
        arbeitnow = {
            "data": [
                {
                    "title": "Python Developer",
                    "company_name": "Acme",
                    "location": "Remote",
                    "url": "https://www.arbeitnow.com/jobs/1",
                    "tags": ["Python"],
                    "description": "Python role.",
                    "created_at": "2026-11-12T00:00:00.000000Z",
                },
                {
                    "title": "Go Developer",
                    "company_name": "Acme",
                    "location": "Remote",
                    "url": "https://www.arbeitnow.com/jobs/2",
                    "tags": ["Go"],
                    "description": "Go role.",
                    "created_at": "2026-11-12T00:00:00.000000Z",
                },
            ]
        }
        remoteok = [
            {"legal": "notice"},
            {
                "position": "Python Engineer",
                "company": "Beta",
                "location": "Remote",
                "url": "https://remoteok.com/remote-jobs/9",
                "tags": ["Python", "FastAPI"],
                "description": "Python + FastAPI role.",
                "date": "2026-11-11T00:00:00+00:00",
            },
        ]

        def fake_fetch(url):
            if "arbeitnow" in url:
                return arbeitnow
            if "remoteok" in url:
                return remoteok
            return None

        with mock.patch.object(jobs, "_fetch_json", side_effect=fake_fetch) as fetch:
            first = jobs.fetch_jobs(["Python", "FastAPI"])
            self.assertEqual(len(first), 2)
            self.assertEqual(first[0]["title"], "Python Engineer")
            self.assertEqual(first[1]["title"], "Python Developer")
            # Second call is served from cache — no more fetches.
            calls_after_first = fetch.call_count
            second = jobs.fetch_jobs(["Python", "FastAPI"])
            self.assertEqual(second, first)
            self.assertEqual(fetch.call_count, calls_after_first)


if __name__ == "__main__":
    unittest.main()
