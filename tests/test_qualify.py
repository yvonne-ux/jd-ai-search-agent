"""Unit tests for Workflow 4 — Candidate Qualification Summary.

Covers the non-API parts: prompt loading, role context parsing, action
normalization, summary formatting, and saving. Run from the project root:
    python -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from agent.models import QualificationSummary
from agent.prompts import load_prompt
from workflows.qualify import (
    SYSTEM_FILE,
    USER_FILE,
    QualifyContext,
    format_summary,
    normalize_action,
    save_summary,
)


class PromptTests(unittest.TestCase):
    def test_qualify_prompts_load(self):
        system = load_prompt(SYSTEM_FILE)
        self.assertIn("JonDavidson", system)
        self.assertIn("recommended_action", system)

    def test_user_template_has_expected_placeholders(self):
        template = load_prompt(USER_FILE)
        for placeholder in ("{{role_title}}", "{{client_type}}",
                            "{{must_have}}", "{{full_message_thread}}"):
            self.assertIn(placeholder, template)


class QualifyContextTests(unittest.TestCase):
    def test_from_intake_file_uses_industry_as_client_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "criteria.json"
            path.write_text(json.dumps({
                "brief": {
                    "role_title": "CFO",
                    "industry": "Logistics",
                    "location": "Singapore",
                    "must_have": "IPO track record",
                },
            }), encoding="utf-8")
            context = QualifyContext.from_intake_file(path)
            self.assertEqual(context.role_title, "CFO")
            self.assertEqual(context.client_type, "Logistics")
            self.assertEqual(context.location, "Singapore")
            self.assertEqual(context.must_have, "IPO track record")

    def test_from_intake_file_falls_back_to_client_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "criteria.json"
            path.write_text(json.dumps({
                "brief": {"role_title": "CFO", "client_name": "Acme Group"},
            }), encoding="utf-8")
            context = QualifyContext.from_intake_file(path)
            self.assertEqual(context.client_type, "Acme Group")


class NormalizeActionTests(unittest.TestCase):
    def test_known_actions(self):
        self.assertEqual(normalize_action("progress"), "Progress to call")
        self.assertEqual(normalize_action("Progress to call"), "Progress to call")
        self.assertEqual(normalize_action("call"), "Progress to call")
        self.assertEqual(normalize_action("HOLD"), "Hold")
        self.assertEqual(normalize_action(" archive "), "Archive")

    def test_unknown_action_returns_none(self):
        self.assertIsNone(normalize_action("maybe later"))
        self.assertIsNone(normalize_action(""))


class FormatSummaryTests(unittest.TestCase):
    def test_format_includes_key_fields(self):
        summary = QualificationSummary(
            candidate_name="David Wong",
            current_role="CFO, SeaFreight Holdings",
            interest_level="Medium",
            availability="Open",
            location_fit="Yes",
            key_positives=["IPO appetite"],
            concerns=["Three-month notice period"],
            recommended_action="Progress to call",
            summary="Strong regional finance leader.",
        )
        text = format_summary(summary)
        self.assertIn("David Wong", text)
        self.assertIn("Interest level: Medium", text)
        self.assertIn("IPO appetite", text)
        self.assertIn("Three-month notice period", text)
        self.assertIn("Progress to call", text)

    def test_format_handles_empty_lists(self):
        text = format_summary(QualificationSummary(candidate_name="Test"))
        self.assertIn("(none)", text)


class SaveSummaryTests(unittest.TestCase):
    def test_save_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = QualificationSummary(
                candidate_name="David Wong",
                recommended_action="Progress to call",
            )
            path = save_summary(summary, out_dir=Path(tmp))
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "david-wong.json")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                saved["qualification_summary"]["candidate_name"], "David Wong"
            )

    def test_save_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = QualificationSummary(candidate_name="David Wong")
            first = save_summary(summary, out_dir=Path(tmp))
            second = save_summary(summary, out_dir=Path(tmp))
            self.assertNotEqual(first, second)
            self.assertEqual(second.name, "david-wong-2.json")


if __name__ == "__main__":
    unittest.main()
