"""Unit tests for the Step 2 shared foundations.

Run from the project root:
    python -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path

from adapters.dripify_export import export_inmail, export_inmails
from adapters.linkedin_csv import load_candidates
from agent.claude_client import ClaudeClient, ClaudeError, extract_json
from agent.logger import log_run
from agent.models import (
    Candidate,
    Longlist,
    LonglistEntry,
    QualificationSummary,
    SearchCriteria,
)

SAMPLE_CSV = Path(__file__).resolve().parent / "sample_rps_export.csv"


class ExtractJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_bare_fenced(self):
        self.assertEqual(extract_json('```\n[1, 2, 3]\n```'), [1, 2, 3])

    def test_json_with_preamble(self):
        text = 'Here is the result:\n{"ok": true}\nThanks.'
        self.assertEqual(extract_json(text), {"ok": True})

    def test_no_json_raises(self):
        with self.assertRaises(ClaudeError):
            extract_json("there is no json here")


class CsvAdapterTests(unittest.TestCase):
    def setUp(self):
        self.candidates = load_candidates(SAMPLE_CSV)

    def test_row_count(self):
        self.assertEqual(len(self.candidates), 3)

    def test_first_last_name_combined(self):
        self.assertEqual(self.candidates[0].name, "Jane Tan")

    def test_fields_mapped(self):
        jane = self.candidates[0]
        self.assertEqual(jane.current_title, "VP Engineering")
        self.assertEqual(jane.current_company, "Acme Tech")
        self.assertEqual(jane.prev_company, "Globex")
        self.assertEqual(jane.location, "Singapore")
        self.assertEqual(jane.profile_url, "https://linkedin.com/in/janetan")

    def test_skills_split_on_comma(self):
        self.assertEqual(
            self.candidates[0].skills,
            ["Python", "Leadership", "Cloud Architecture"],
        )

    def test_skills_split_on_semicolon(self):
        self.assertEqual(
            self.candidates[1].skills,
            ["Product Strategy", "Roadmapping", "Analytics"],
        )

    def test_raw_preserves_columns(self):
        self.assertIn("Tenure", self.candidates[0].raw)

    def test_mapped_columns_excluded_from_attributes(self):
        # Every column in the sample CSV maps to a core field, so there are
        # no leftover attributes.
        self.assertEqual(self.candidates[0].attributes, {})

    def test_unmapped_columns_captured_as_attributes(self):
        import tempfile
        from pathlib import Path

        csv_text = (
            "First Name,Last Name,Title,Company,"
            "Siemens NX (yrs),Aerospace Exp (yrs),Bachelor Degree\n"
            "Ranga,Rajan,Process Engineer,ST Engineering,3,3,Yes\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extra.csv"
            path.write_text(csv_text, encoding="utf-8")
            candidate = load_candidates(path)[0]

        self.assertEqual(candidate.attributes["Siemens NX (yrs)"], "3")
        self.assertEqual(candidate.attributes["Aerospace Exp (yrs)"], "3")
        self.assertEqual(candidate.attributes["Bachelor Degree"], "Yes")
        # Core columns and the name parts are not duplicated into attributes.
        self.assertNotIn("Title", candidate.attributes)
        self.assertNotIn("First Name", candidate.attributes)


class ModelTests(unittest.TestCase):
    def test_search_criteria_round_trip(self):
        data = {
            "job_titles": ["CFO", "Finance Director"],
            "seniority_levels": ["C-Suite"],
            "target_companies": ["Acme", "Globex"],
            "industries": ["Banking"],
            "locations": ["Singapore"],
            "boolean_string": '("CFO" OR "Finance Director")',
            "exclusions": ["Junior"],
            "search_rationale": "Targets senior finance leaders.",
        }
        criteria = SearchCriteria.from_dict(data)
        self.assertEqual(criteria.job_titles, ["CFO", "Finance Director"])
        self.assertEqual(criteria.to_dict(), data)

    def test_search_criteria_tolerates_missing_keys(self):
        criteria = SearchCriteria.from_dict({})
        self.assertEqual(criteria.job_titles, [])
        self.assertEqual(criteria.boolean_string, "")

    def test_str_value_coerced_to_list(self):
        criteria = SearchCriteria.from_dict({"job_titles": "CFO"})
        self.assertEqual(criteria.job_titles, ["CFO"])

    def test_qualification_summary_round_trip(self):
        data = {
            "candidate_name": "Jane Tan",
            "current_role": "VP Engineering",
            "interest_level": "High",
            "availability": "Open",
            "location_fit": "Yes",
            "key_positives": ["Strong leadership"],
            "concerns": ["Notice period"],
            "recommended_action": "Progress to call",
            "summary": "Strong fit.",
        }
        summary = QualificationSummary.from_dict(data)
        self.assertEqual(summary.to_dict(), data)

    def test_longlist_from_keyed_dict(self):
        data = {
            "longlist": [
                {"rank": "1", "candidate_name": "Jane Tan", "fit_score": "9"},
            ],
            "search_commentary": "Healthy response rate.",
        }
        longlist = Longlist.from_dict(data)
        self.assertEqual(len(longlist.entries), 1)
        self.assertEqual(longlist.entries[0].rank, 1)
        self.assertEqual(longlist.entries[0].fit_score, 9)
        self.assertEqual(longlist.search_commentary, "Healthy response rate.")

    def test_longlist_from_bare_list(self):
        longlist = Longlist.from_dict([{"rank": 1, "candidate_name": "Jane Tan"}])
        self.assertEqual(len(longlist.entries), 1)
        self.assertEqual(longlist.search_commentary, "")

    def test_longlist_entry_handles_bad_int(self):
        entry = LonglistEntry.from_dict({"rank": "not-a-number"})
        self.assertEqual(entry.rank, 0)


class DripifyExportTests(unittest.TestCase):
    def test_export_single_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = export_inmail("Jane Tan", "Hello Jane.", out_dir=Path(tmp))
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "jane-tan.txt")
            self.assertEqual(path.read_text(encoding="utf-8"), "Hello Jane.\n")

    def test_name_collision_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = export_inmail("Jane Tan", "Draft one.", out_dir=Path(tmp))
            second = export_inmail("Jane Tan", "Draft two.", out_dir=Path(tmp))
            self.assertNotEqual(first, second)
            self.assertEqual(second.name, "jane-tan-2.txt")

    def test_export_many(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_inmails(
                [("Jane Tan", "Hi Jane."), ("Marcus Lee", "Hi Marcus.")],
                out_dir=Path(tmp),
            )
            self.assertEqual(len(paths), 2)
            self.assertTrue(all(p.exists() for p in paths))


class LoggerTests(unittest.TestCase):
    def test_log_run_writes_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = log_run(
                workflow="intake",
                model="claude-sonnet-4-6",
                inputs={"client": "Acme"},
                system_prompt="system",
                user_prompt="user",
                output={"job_titles": ["CFO"]},
                runs_dir=Path(tmp),
            )
            self.assertTrue(path.exists())
            self.assertIn("intake", path.name)
            self.assertIn('"workflow": "intake"', path.read_text(encoding="utf-8"))


class ClaudeClientTests(unittest.TestCase):
    def test_placeholder_key_rejected(self):
        with self.assertRaises(ClaudeError):
            ClaudeClient(api_key="sk-ant-xxxxxxxx")


if __name__ == "__main__":
    unittest.main()
