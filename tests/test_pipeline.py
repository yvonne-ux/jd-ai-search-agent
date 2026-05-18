"""Unit tests for pipeline orchestration.

Covers mandate workspace creation. Run from the project root:
    python -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path

from workflows.pipeline import Mandate, create_mandate


class CreateMandateTests(unittest.TestCase):
    def test_creates_workspace_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            mandate = create_mandate("Acme Corp CFO", base_dir=Path(tmp))
            self.assertIsInstance(mandate, Mandate)
            self.assertTrue(mandate.folder.is_dir())
            self.assertEqual(mandate.folder.name, "acme-corp-cfo")

    def test_collision_gets_a_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = create_mandate("Acme CFO", base_dir=Path(tmp))
            second = create_mandate("Acme CFO", base_dir=Path(tmp))
            self.assertNotEqual(first.folder, second.folder)
            self.assertEqual(second.folder.name, "acme-cfo-2")

    def test_subfolder_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            mandate = create_mandate("Acme CFO", base_dir=Path(tmp))
            self.assertEqual(mandate.inmail_dir.parent, mandate.folder)
            self.assertEqual(mandate.inmail_dir.name, "inmail_drafts")
            self.assertEqual(mandate.qualifications_dir.name, "qualifications")

    def test_blank_name_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            mandate = create_mandate("", base_dir=Path(tmp))
            self.assertEqual(mandate.folder.name, "mandate")


if __name__ == "__main__":
    unittest.main()
