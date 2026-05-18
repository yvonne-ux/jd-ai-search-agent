"""Pipeline orchestration — per-mandate workspaces for end-to-end runs.

A mandate workspace is a folder under data/mandates/ that groups every
artifact for one search: search criteria, ranking, InMail drafts,
qualification summaries, and the final longlist.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_MANDATES_DIR = Path(__file__).resolve().parent.parent / "data" / "mandates"


def _slug(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "mandate"


@dataclass
class Mandate:
    """A workspace folder grouping all artifacts for one search mandate."""

    name: str
    folder: Path

    @property
    def inmail_dir(self) -> Path:
        return self.folder / "inmail_drafts"

    @property
    def qualifications_dir(self) -> Path:
        return self.folder / "qualifications"


def create_mandate(name: str, base_dir: Optional[Path] = None) -> Mandate:
    """Create a fresh mandate workspace folder and return a Mandate."""
    base = Path(base_dir) if base_dir else _MANDATES_DIR
    slug = _slug(name)

    folder = base / slug
    counter = 2
    while folder.exists():
        folder = base / f"{slug}-{counter}"
        counter += 1

    folder.mkdir(parents=True)
    return Mandate(name=name, folder=folder)
