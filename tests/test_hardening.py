"""Unit tests for Step 9 hardening — token usage tracking and cost summary.

Run from the project root:
    python -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from agent.claude_client import usage_dict
from agent.logger import log_run, summarize_runs


class _FakeUsage:
    """Stand-in for an Anthropic response usage object."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class UsageDictTests(unittest.TestCase):
    def test_extracts_all_keys(self):
        usage = _FakeUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=80,
        )
        self.assertEqual(usage_dict(usage), {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 20,
            "cache_read_input_tokens": 80,
        })

    def test_missing_attributes_default_to_zero(self):
        usage = _FakeUsage(input_tokens=100, output_tokens=50)
        result = usage_dict(usage)
        self.assertEqual(result["cache_read_input_tokens"], 0)
        self.assertEqual(result["cache_creation_input_tokens"], 0)

    def test_none_values_become_zero(self):
        usage = _FakeUsage(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=None,
            cache_read_input_tokens=None,
        )
        result = usage_dict(usage)
        self.assertEqual(result["cache_read_input_tokens"], 0)


class LogRunUsageTests(unittest.TestCase):
    def test_usage_is_written_to_the_run_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = log_run(
                workflow="intake",
                model="claude-sonnet-4-6",
                inputs={},
                system_prompt="s",
                user_prompt="u",
                output={},
                usage={"input_tokens": 123, "output_tokens": 45,
                       "cache_creation_input_tokens": 0,
                       "cache_read_input_tokens": 67},
                runs_dir=Path(tmp),
            )
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["usage"]["input_tokens"], 123)
            self.assertEqual(record["usage"]["cache_read_input_tokens"], 67)

    def test_usage_defaults_to_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = log_run(
                workflow="intake",
                model="claude-sonnet-4-6",
                inputs={},
                system_prompt="s",
                user_prompt="u",
                output={},
                runs_dir=Path(tmp),
            )
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["usage"], {})


class SummarizeRunsTests(unittest.TestCase):
    def _write_run(self, folder, workflow, usage):
        log_run(
            workflow=workflow,
            model="claude-sonnet-4-6",
            inputs={},
            system_prompt="s",
            user_prompt="u",
            output={},
            usage=usage,
            runs_dir=folder,
        )

    def test_aggregates_by_workflow_and_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._write_run(folder, "intake", {
                "input_tokens": 100, "output_tokens": 20,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0})
            self._write_run(folder, "rank", {
                "input_tokens": 200, "output_tokens": 60,
                "cache_creation_input_tokens": 10,
                "cache_read_input_tokens": 90})

            summary = summarize_runs(folder)
            self.assertEqual(summary["run_count"], 2)
            self.assertEqual(summary["total"]["input_tokens"], 300)
            self.assertEqual(summary["total"]["output_tokens"], 80)
            self.assertEqual(summary["total"]["cache_read_input_tokens"], 90)
            self.assertEqual(summary["by_workflow"]["rank"]["runs"], 1)
            self.assertEqual(
                summary["by_workflow"]["intake"]["input_tokens"], 100
            )

    def test_missing_directory_returns_zeroed_summary(self):
        summary = summarize_runs("/no/such/runs/dir")
        self.assertEqual(summary["run_count"], 0)
        self.assertEqual(summary["total"]["input_tokens"], 0)

    def test_skips_unparseable_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._write_run(folder, "intake", {
                "input_tokens": 100, "output_tokens": 20,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0})
            (folder / "broken.json").write_text("{not json", encoding="utf-8")
            summary = summarize_runs(folder)
            self.assertEqual(summary["run_count"], 1)


if __name__ == "__main__":
    unittest.main()
