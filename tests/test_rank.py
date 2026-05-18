"""Unit tests for Workflow 2 — Candidate Ranking.

Covers the non-API parts: prompt loading, criteria loading from an intake file,
the CandidateRanking model, and ranking display. Run from the project root:
    python -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from agent.models import CandidateRanking
from agent.prompts import load_prompt
from workflows.rank import (
    SYSTEM_FILE,
    USER_FILE,
    format_rankings,
    load_criteria_from_intake,
    save_rankings,
)


class PromptTests(unittest.TestCase):
    def test_rank_prompts_load(self):
        system = load_prompt(SYSTEM_FILE)
        self.assertIn("JonDavidson", system)
        self.assertIn("rankings", system)

    def test_user_template_has_expected_placeholders(self):
        template = load_prompt(USER_FILE)
        for placeholder in ("{{criteria}}", "{{candidates}}",
                            "{{candidate_count}}"):
            self.assertIn(placeholder, template)


class CriteriaLoadingTests(unittest.TestCase):
    def test_loads_search_criteria_from_intake_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "criteria.json"
            path.write_text(json.dumps({
                "brief": {"role_title": "CFO"},
                "search_criteria": {
                    "job_titles": ["CFO", "Finance Director"],
                    "boolean_string": '("CFO")',
                },
            }), encoding="utf-8")
            criteria = load_criteria_from_intake(path)
            self.assertEqual(criteria.job_titles, ["CFO", "Finance Director"])
            self.assertEqual(criteria.boolean_string, '("CFO")')

    def test_accepts_bare_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "criteria.json"
            path.write_text(json.dumps({"job_titles": ["CFO"]}), encoding="utf-8")
            criteria = load_criteria_from_intake(path)
            self.assertEqual(criteria.job_titles, ["CFO"])


class CandidateRankingModelTests(unittest.TestCase):
    def test_round_trip(self):
        data = {
            "rank": 1,
            "candidate_name": "Jane Tan",
            "current_title": "VP Engineering",
            "current_company": "Acme Tech",
            "fit_score": 9,
            "matches": ["Senior leadership"],
            "gaps": ["No IPO experience"],
            "recommendation": "Prioritise",
        }
        ranking = CandidateRanking.from_dict(data)
        self.assertEqual(ranking.to_dict(), data)

    def test_coerces_string_numbers(self):
        ranking = CandidateRanking.from_dict({"rank": "2", "fit_score": "7"})
        self.assertEqual(ranking.rank, 2)
        self.assertEqual(ranking.fit_score, 7)


class FormatRankingsTests(unittest.TestCase):
    def test_format_includes_rank_and_recommendation(self):
        rankings = [
            CandidateRanking(
                rank=1,
                candidate_name="Jane Tan",
                current_title="VP Engineering",
                current_company="Acme Tech",
                fit_score=9,
                matches=["Senior leader"],
                gaps=["No IPO"],
                recommendation="Prioritise",
            ),
        ]
        text = format_rankings(rankings)
        self.assertIn("#1", text)
        self.assertIn("Jane Tan", text)
        self.assertIn("Fit 9/10", text)
        self.assertIn("Prioritise", text)
        self.assertIn("Senior leader", text)

    def test_format_handles_empty_list(self):
        self.assertEqual(format_rankings([]), "(no candidates ranked)")


class SaveRankingsTests(unittest.TestCase):
    def test_save_writes_rankings(self):
        with tempfile.TemporaryDirectory() as tmp:
            rankings = [CandidateRanking(rank=1, candidate_name="Jane Tan")]
            path = save_rankings(rankings, "acme-cfo", out_dir=Path(tmp))
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "acme-cfo.json")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["rankings"][0]["candidate_name"], "Jane Tan")

    def test_save_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = save_rankings([], "acme-cfo", out_dir=Path(tmp))
            second = save_rankings([], "acme-cfo", out_dir=Path(tmp))
            self.assertNotEqual(first, second)
            self.assertEqual(second.name, "acme-cfo-2.json")


if __name__ == "__main__":
    unittest.main()
