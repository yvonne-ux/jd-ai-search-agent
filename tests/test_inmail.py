"""Unit tests for Workflow 2 — Personalised InMail Draft.

Covers the non-API parts: prompt loading, role context parsing, and the draft
quality check. Run from the project root:
    python -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from agent.prompts import load_prompt
from workflows.inmail import (
    BANNED_PHRASES,
    MAX_WORDS,
    SYSTEM_FILE,
    USER_FILE,
    RoleContext,
    check_draft,
)


class PromptTests(unittest.TestCase):
    def test_inmail_prompts_load(self):
        system = load_prompt(SYSTEM_FILE)
        self.assertIn("JonDavidson", system)
        self.assertIn("150 words", system)

    def test_user_template_has_expected_placeholders(self):
        template = load_prompt(USER_FILE)
        for placeholder in ("{{candidate_name}}", "{{role_title}}",
                            "{{selling_point}}"):
            self.assertIn(placeholder, template)


class RoleContextTests(unittest.TestCase):
    def test_from_intake_file_reads_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "criteria.json"
            path.write_text(json.dumps({
                "brief": {
                    "role_title": "Chief Financial Officer",
                    "seniority": "C-Suite",
                    "location": "Singapore",
                },
                "search_criteria": {},
            }), encoding="utf-8")
            role = RoleContext.from_intake_file(path, selling_point="IPO-bound")
            self.assertEqual(role.role_title, "Chief Financial Officer")
            self.assertEqual(role.seniority, "C-Suite")
            self.assertEqual(role.role_location, "Singapore")
            self.assertEqual(role.selling_point, "IPO-bound")

    def test_from_intake_file_accepts_bare_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brief.json"
            path.write_text(json.dumps({"role_title": "CFO"}), encoding="utf-8")
            role = RoleContext.from_intake_file(path)
            self.assertEqual(role.role_title, "CFO")
            self.assertEqual(role.selling_point, "")


class CheckDraftTests(unittest.TestCase):
    def test_clean_draft_has_no_warnings(self):
        draft = "Hi Jane, your work leading finance at Acme stood out. " \
                "Our client is hiring a CFO. Open to a brief conversation?"
        self.assertEqual(check_draft(draft), [])

    def test_over_length_draft_warns(self):
        draft = "word " * (MAX_WORDS + 10)
        warnings = check_draft(draft)
        self.assertEqual(len(warnings), 1)
        self.assertIn("over the", warnings[0])

    def test_banned_phrase_warns(self):
        draft = "I came across your profile and wanted to reach out."
        warnings = check_draft(draft)
        self.assertTrue(any("discouraged phrase" in w for w in warnings))

    def test_banned_phrase_detection_is_case_insensitive(self):
        draft = "This is an EXCITING OPPORTUNITY for you."
        warnings = check_draft(draft)
        self.assertTrue(any("exciting opportunity" in w for w in warnings))

    def test_all_banned_phrases_are_detected(self):
        for phrase in BANNED_PHRASES:
            warnings = check_draft(f"Some text {phrase} more text.")
            self.assertTrue(
                any("discouraged phrase" in w for w in warnings),
                msg=f"phrase not flagged: {phrase}",
            )


if __name__ == "__main__":
    unittest.main()
