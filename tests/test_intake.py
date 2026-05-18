"""Unit tests for Workflow 1 — Intake to Search Criteria.

Covers the non-API parts: prompt loading, template filling, brief parsing,
criteria formatting, and saving. Run from the project root:
    python -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from agent.models import SearchCriteria
from agent.prompts import fill_template, load_prompt
from workflows.intake import (
    BRIEF_FIELDS,
    MandateBrief,
    SYSTEM_FILE,
    USER_FILE,
    format_criteria,
    save_criteria,
)


class PromptTests(unittest.TestCase):
    def test_intake_prompts_load(self):
        self.assertIn("JonDavidson", load_prompt(SYSTEM_FILE))
        self.assertIn("{{role_title}}", load_prompt(USER_FILE))

    def test_fill_template_replaces_placeholders(self):
        result = fill_template("Role: {{role_title}}", role_title="CFO")
        self.assertEqual(result, "Role: CFO")

    def test_fill_template_leaves_unknown_placeholder(self):
        result = fill_template("Role: {{role_title}}", client_name="Acme")
        self.assertEqual(result, "Role: {{role_title}}")


class MandateBriefTests(unittest.TestCase):
    def test_from_dict_keeps_known_fields(self):
        brief = MandateBrief.from_dict({"client_name": " Acme ", "role_title": "CFO"})
        self.assertEqual(brief.client_name, "Acme")
        self.assertEqual(brief.role_title, "CFO")

    def test_from_dict_ignores_unknown_fields(self):
        brief = MandateBrief.from_dict({"role_title": "CFO", "junk": "ignored"})
        self.assertEqual(brief.role_title, "CFO")

    def test_as_prompt_values_marks_blanks(self):
        brief = MandateBrief(role_title="CFO")
        values = brief.as_prompt_values()
        self.assertEqual(values["role_title"], "CFO")
        self.assertEqual(values["nice_to_have"], "(none specified)")

    def test_as_prompt_values_covers_all_brief_fields(self):
        values = MandateBrief().as_prompt_values()
        for field, _ in BRIEF_FIELDS:
            self.assertIn(field, values)

    def test_user_template_placeholders_match_brief_fields(self):
        template = load_prompt(USER_FILE)
        for field, _ in BRIEF_FIELDS:
            self.assertIn("{{" + field + "}}", template)


class FormatCriteriaTests(unittest.TestCase):
    def test_format_includes_boolean_and_rationale(self):
        criteria = SearchCriteria(
            job_titles=["CFO"],
            boolean_string='("CFO")',
            search_rationale="Targets finance leaders.",
        )
        text = format_criteria(criteria)
        self.assertIn("CFO", text)
        self.assertIn('("CFO")', text)
        self.assertIn("Targets finance leaders.", text)

    def test_format_handles_empty_sections(self):
        text = format_criteria(SearchCriteria())
        self.assertIn("(none)", text)


class SaveCriteriaTests(unittest.TestCase):
    def test_save_writes_brief_and_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = MandateBrief(client_name="Acme Corp", role_title="CFO")
            criteria = SearchCriteria(job_titles=["CFO"])
            path = save_criteria(criteria, brief, out_dir=Path(tmp))
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "acme-corp_cfo.json")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["brief"]["client_name"], "Acme Corp")
            self.assertEqual(saved["search_criteria"]["job_titles"], ["CFO"])

    def test_save_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = MandateBrief(client_name="Acme", role_title="CFO")
            criteria = SearchCriteria()
            first = save_criteria(criteria, brief, out_dir=Path(tmp))
            second = save_criteria(criteria, brief, out_dir=Path(tmp))
            self.assertNotEqual(first, second)
            self.assertEqual(second.name, "acme_cfo-2.json")


if __name__ == "__main__":
    unittest.main()
