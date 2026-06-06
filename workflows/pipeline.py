"""Pipeline orchestration — per-mandate workspaces for end-to-end runs.

A mandate workspace is a folder under data/mandates/ that groups every
artifact for one search: search criteria, ranking, InMail drafts,
qualification summaries, and the final longlist.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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
    # Persist the human-readable name so list_mandates can recover it later.
    (folder / ".name").write_text(name, encoding="utf-8")
    return Mandate(name=name, folder=folder)


def list_mandates(base_dir: Optional[Path] = None) -> List[Mandate]:
    """Return every existing mandate workspace, newest folder first.

    The display name is taken from a stored .name file if present (set when a
    mandate is created via the web UI), otherwise it is derived from the slug.
    """
    base = Path(base_dir) if base_dir else _MANDATES_DIR
    if not base.exists():
        return []

    mandates: List[Mandate] = []
    for folder in sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        name_file = folder / ".name"
        if name_file.exists():
            name = name_file.read_text(encoding="utf-8").strip()
        else:
            name = folder.name.replace("-", " ").title()
        mandates.append(Mandate(name=name, folder=folder))
    return mandates


def load_mandate(slug: str, base_dir: Optional[Path] = None) -> Optional[Mandate]:
    """Look up a mandate by its folder slug. Returns None if not found."""
    base = Path(base_dir) if base_dir else _MANDATES_DIR
    folder = base / slug
    if not folder.is_dir():
        return None
    name_file = folder / ".name"
    if name_file.exists():
        name = name_file.read_text(encoding="utf-8").strip()
    else:
        name = folder.name.replace("-", " ").title()
    return Mandate(name=name, folder=folder)
