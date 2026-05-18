"""Dripify text-file exporter.

Writes personalised InMail drafts to plain .txt files (one per candidate) so a
consultant can review, edit, and copy them into the Dripify dashboard. There is
no live Dripify integration in Phase 1A.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "inmail_drafts"


def _safe_filename(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name or "").strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "candidate"


def export_inmail(
    candidate_name: str,
    draft: str,
    out_dir: Optional[Path] = None,
) -> Path:
    """Write one InMail draft to a .txt file and return its path."""
    target = Path(out_dir) if out_dir else _DEFAULT_DIR
    target.mkdir(parents=True, exist_ok=True)

    base = _safe_filename(candidate_name)
    path = target / f"{base}.txt"
    # Avoid clobbering when two candidates share a name.
    counter = 2
    while path.exists():
        path = target / f"{base}-{counter}.txt"
        counter += 1

    path.write_text(draft.strip() + "\n", encoding="utf-8")
    return path


def export_inmails(
    drafts: Iterable[Tuple[str, str]],
    out_dir: Optional[Path] = None,
) -> List[Path]:
    """Write multiple drafts. drafts is an iterable of (candidate_name, text)."""
    return [export_inmail(name, text, out_dir) for name, text in drafts]
