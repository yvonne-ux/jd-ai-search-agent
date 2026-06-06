"""Mandate-scoped persistence for the web UI.

The web app reads and writes the *same* on-disk layout the CLI uses inside a
mandate workspace (``data/mandates/<slug>/``), so a consultant can move a
mandate between the CLI and the browser:

    criteria.json        {"brief": {...}, "search_criteria": {...}}
    candidates.csv       LinkedIn RPS export (uploaded on the Ranking screen)
    ranking.json         {"rankings": [...]}
    selection.json       {"selected": [candidate names]}   (web-only)
    selling_point.txt    InMail selling point
    inmail_drafts/        one <candidate>.txt per draft

``criteria.json`` is the combined brief+criteria file the CLI's
``save_criteria`` produces, so ``load_criteria_from_intake`` (Ranking) and
``RoleContext.from_intake_file`` (InMail) read it without modification. Unlike
the CLI helpers — which auto-number to avoid clobbering — these write to fixed
filenames so the web app's "edit and save" actions overwrite in place.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from agent.models import Candidate, CandidateRanking, SearchCriteria
from workflows.intake import MandateBrief
from workflows.pipeline import Mandate

CRITERIA_FILE = "criteria.json"
CANDIDATES_FILE = "candidates.csv"
RANKING_FILE = "ranking.json"
SELECTION_FILE = "selection.json"
SELLING_POINT_FILE = "selling_point.txt"
JD_SOURCE_FILE = "jd_source.txt"  # raw text of the uploaded JD (web-only)


def _safe_filename(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name or "").strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "candidate"


# ---------- Intake: brief + criteria ----------

def save_intake(mandate: Mandate, brief: MandateBrief, criteria: SearchCriteria) -> Path:
    """Write the combined brief+criteria file (CLI-compatible)."""
    path = mandate.folder / CRITERIA_FILE
    record = {"brief": asdict(brief), "search_criteria": criteria.to_dict()}
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_criteria_edits(mandate: Mandate, criteria: SearchCriteria) -> Path:
    """Persist edited criteria in place, preserving the stored brief."""
    path = mandate.folder / CRITERIA_FILE
    existing = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    brief = existing.get("brief", {})
    record = {"brief": brief, "search_criteria": criteria.to_dict()}
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def criteria_path(mandate: Mandate) -> Path:
    return mandate.folder / CRITERIA_FILE


def has_criteria(mandate: Mandate) -> bool:
    return criteria_path(mandate).exists()


def load_brief(mandate: Mandate) -> Optional[MandateBrief]:
    path = criteria_path(mandate)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return MandateBrief.from_dict(data.get("brief", {}))


def load_criteria(mandate: Mandate) -> Optional[SearchCriteria]:
    path = criteria_path(mandate)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return SearchCriteria.from_dict(data.get("search_criteria", data))


# ---------- JD source text (raw upload, web-only) ----------

def jd_source_path(mandate: Mandate) -> Path:
    return mandate.folder / JD_SOURCE_FILE


def has_jd_source(mandate: Mandate) -> bool:
    return jd_source_path(mandate).exists()


def save_jd_source(mandate: Mandate, text: str) -> Path:
    """Persist the full text of the uploaded JD so it can be sent to Claude
    alongside the brief. Kept as a sibling of ``brief.json`` for auditability."""
    path = jd_source_path(mandate)
    path.write_text(text or "", encoding="utf-8")
    return path


def load_jd_source(mandate: Mandate) -> Optional[str]:
    path = jd_source_path(mandate)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def clear_jd_source(mandate: Mandate) -> None:
    path = jd_source_path(mandate)
    if path.exists():
        path.unlink()


# ---------- Ranking: CSV + rankings ----------

def candidates_csv_path(mandate: Mandate) -> Path:
    return mandate.folder / CANDIDATES_FILE


def has_candidates_csv(mandate: Mandate) -> bool:
    return candidates_csv_path(mandate).exists()


def save_candidates_csv(mandate: Mandate, raw_bytes: bytes) -> Path:
    path = candidates_csv_path(mandate)
    path.write_bytes(raw_bytes)
    return path


def ranking_path(mandate: Mandate) -> Path:
    return mandate.folder / RANKING_FILE


def save_rankings(mandate: Mandate, rankings: List[CandidateRanking]) -> Path:
    path = ranking_path(mandate)
    path.write_text(
        json.dumps(
            {"rankings": [r.to_dict() for r in rankings]},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def load_rankings(mandate: Mandate) -> List[CandidateRanking]:
    path = ranking_path(mandate)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rankings", data) if isinstance(data, dict) else data
    return [CandidateRanking.from_dict(r) for r in rows]


# ---------- Selection carried from Ranking to InMail ----------

def save_selection(mandate: Mandate, names: List[str]) -> Path:
    path = mandate.folder / SELECTION_FILE
    path.write_text(
        json.dumps({"selected": names}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def load_selection(mandate: Mandate) -> List[str]:
    path = mandate.folder / SELECTION_FILE
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [str(n) for n in data.get("selected", [])]


# ---------- InMail: selling point + drafts ----------

def save_selling_point(mandate: Mandate, text: str) -> Path:
    path = mandate.folder / SELLING_POINT_FILE
    path.write_text((text or "").strip() + "\n", encoding="utf-8")
    return path


def load_selling_point(mandate: Mandate) -> str:
    path = mandate.folder / SELLING_POINT_FILE
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def draft_path(mandate: Mandate, candidate_name: str) -> Path:
    return mandate.inmail_dir / f"{_safe_filename(candidate_name)}.txt"


def save_draft(mandate: Mandate, candidate_name: str, text: str) -> Path:
    """Write/overwrite one candidate's InMail draft in place."""
    mandate.inmail_dir.mkdir(parents=True, exist_ok=True)
    path = draft_path(mandate, candidate_name)
    path.write_text((text or "").strip() + "\n", encoding="utf-8")
    return path


def load_draft(mandate: Mandate, candidate_name: str) -> Optional[str]:
    path = draft_path(mandate, candidate_name)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()
