"""Workflow 1 — Intake to Search Criteria.

Converts a client mandate brief into a structured SearchCriteria object,
including a ready-to-paste LinkedIn RPS Boolean string. Implements Prompt 1
from the developer brief.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.claude_client import MODEL_SONNET, ClaudeClient
from agent.logger import log_run
from agent.models import SearchCriteria
from agent.prompts import fill_template, load_prompt

WORKFLOW = "intake"
SYSTEM_FILE = "intake_system.txt"
USER_FILE = "intake_user.txt"

_CRITERIA_DIR = Path(__file__).resolve().parent.parent / "data" / "search_criteria"

# (field name, human-readable label) — drives interactive collection and display.
# Order is preserved for CLI prompts; the web UI lays the same fields out
# manually to match the step1 design.
BRIEF_FIELDS: List[Tuple[str, str]] = [
    ("client_name", "Client / Company"),
    ("role_title", "Role title"),
    ("industry", "Industry"),
    ("location", "Location"),
    ("seniority", "Level / Seniority"),
    ("responsibilities", "Role summary"),
    ("must_have", "Must-have skills"),
    ("nice_to_have", "Nice-to-have skills"),
    ("exclusions", "Avoid flags"),
]


@dataclass
class MandateBrief:
    """A client brief for one search mandate."""

    client_name: str = ""
    role_title: str = ""
    industry: str = ""
    location: str = ""
    seniority: str = ""
    responsibilities: str = ""
    must_have: str = ""
    nice_to_have: str = ""
    exclusions: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MandateBrief":
        return cls(**{
            field: str(data.get(field, "") or "").strip()
            for field, _ in BRIEF_FIELDS
        })

    def as_prompt_values(self) -> Dict[str, str]:
        """Brief fields ready for the prompt template; blanks read clearly."""
        return {
            field: (value.strip() or "(none specified)")
            for field, value in asdict(self).items()
        }


def generate_search_criteria(
    brief: MandateBrief,
    client: ClaudeClient,
    *,
    jd_text: Optional[str] = None,
    max_tokens: int = 2048,
) -> SearchCriteria:
    """Run Prompt 1 against the brief and return structured SearchCriteria.

    When ``jd_text`` is supplied (the full text extracted from an uploaded JD),
    it is passed to Claude as the authoritative source for sector grounding,
    so target_companies / industries / job_titles reflect the real role rather
    than generic defaults.
    """
    system = load_prompt(SYSTEM_FILE)
    values = brief.as_prompt_values()
    values["jd_source"] = (
        (jd_text or "").strip()
        or "(no JD file uploaded — use the brief fields above)"
    )
    user = fill_template(load_prompt(USER_FILE), **values)

    raw = client.complete_json(
        system=system,
        user=user,
        model=MODEL_SONNET,
        max_tokens=max_tokens,
    )
    log_run(WORKFLOW, MODEL_SONNET, asdict(brief), system, user, raw,
            usage=client.last_usage)
    return SearchCriteria.from_dict(raw)


def format_criteria(criteria: SearchCriteria) -> str:
    """Render SearchCriteria as a readable block for consultant review."""
    def section(label: str, items: List[str]) -> str:
        if not items:
            return f"{label}: (none)"
        return f"{label}:\n  - " + "\n  - ".join(items)

    return "\n".join([
        section("Job titles", criteria.job_titles),
        section("Seniority levels", criteria.seniority_levels),
        section("Target companies", criteria.target_companies),
        section("Industries", criteria.industries),
        section("Locations", criteria.locations),
        section("Exclusions", criteria.exclusions),
        "",
        "Boolean string (paste into LinkedIn RPS):",
        f"  {criteria.boolean_string}",
        "",
        f"Rationale: {criteria.search_rationale}",
    ])


def _slug(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "mandate"


def save_criteria(
    criteria: SearchCriteria,
    brief: MandateBrief,
    out_dir: Optional[Path] = None,
) -> Path:
    """Write the criteria to a JSON file the consultant can review and edit."""
    target = Path(out_dir) if out_dir else _CRITERIA_DIR
    target.mkdir(parents=True, exist_ok=True)

    base = f"{_slug(brief.client_name)}_{_slug(brief.role_title)}"
    path = target / f"{base}.json"
    counter = 2
    while path.exists():
        path = target / f"{base}-{counter}.json"
        counter += 1

    record = {"brief": asdict(brief), "search_criteria": criteria.to_dict()}
    path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
