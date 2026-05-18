"""Workflow 4 — Candidate Qualification Summary.

Assesses a candidate who has replied to outreach, turning their LinkedIn
message thread into a structured QualificationSummary. Implements Prompt 3
from the developer brief.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from agent.claude_client import MODEL_SONNET, ClaudeClient
from agent.logger import log_run
from agent.models import QualificationSummary
from agent.prompts import fill_template, load_prompt

WORKFLOW = "qualify"
SYSTEM_FILE = "qualify_system.txt"
USER_FILE = "qualify_user.txt"

_SUMMARY_DIR = Path(__file__).resolve().parent.parent / "data" / "qualifications"

# Canonical recommended_action values, keyed by the inputs a consultant may type.
_ACTIONS = {
    "progress": "Progress to call",
    "progress to call": "Progress to call",
    "call": "Progress to call",
    "hold": "Hold",
    "archive": "Archive",
}


@dataclass
class QualifyContext:
    """The role context needed to qualify a candidate's reply."""

    role_title: str = ""
    client_type: str = ""
    location: str = ""
    must_have: str = ""

    @classmethod
    def from_intake_file(cls, path) -> "QualifyContext":
        """Build role context from an intake workflow JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        brief = data.get("brief", data)
        return cls(
            role_title=str(brief.get("role_title", "") or "").strip(),
            # client_type is a sector descriptor, not the client's name.
            client_type=str(
                brief.get("industry", "") or brief.get("client_name", "") or ""
            ).strip(),
            location=str(brief.get("location", "") or "").strip(),
            must_have=str(brief.get("must_have", "") or "").strip(),
        )


def normalize_action(text: str) -> Optional[str]:
    """Map a consultant's typed action to a canonical value, or None."""
    return _ACTIONS.get((text or "").strip().lower())


def qualify_candidate(
    thread: str,
    context: QualifyContext,
    client: ClaudeClient,
    *,
    max_tokens: int = 1536,
) -> QualificationSummary:
    """Run Prompt 3 on a reply thread and return a QualificationSummary."""
    system = load_prompt(SYSTEM_FILE)
    user = fill_template(
        load_prompt(USER_FILE),
        role_title=context.role_title or "(not stated)",
        client_type=context.client_type or "(not stated)",
        location=context.location or "(not stated)",
        must_have=context.must_have or "(not stated)",
        full_message_thread=thread.strip(),
    )

    raw = client.complete_json(
        system=system,
        user=user,
        model=MODEL_SONNET,
        max_tokens=max_tokens,
    )
    log_run(
        WORKFLOW,
        MODEL_SONNET,
        {"context": asdict(context), "thread": thread},
        system,
        user,
        raw,
    )
    return QualificationSummary.from_dict(raw)


def format_summary(summary: QualificationSummary) -> str:
    """Render a QualificationSummary as a readable block for review."""
    def section(label: str, items: list) -> str:
        if not items:
            return f"{label}: (none)"
        return f"{label}:\n  - " + "\n  - ".join(items)

    return "\n".join([
        f"Candidate: {summary.candidate_name or 'Unknown'}",
        f"Current role: {summary.current_role or '(not stated)'}",
        f"Interest level: {summary.interest_level or 'n/a'}",
        f"Availability: {summary.availability or 'n/a'}",
        f"Location fit: {summary.location_fit or 'n/a'}",
        section("Key positives", summary.key_positives),
        section("Concerns", summary.concerns),
        f"Recommended action: {summary.recommended_action or 'n/a'}",
        "",
        f"Summary: {summary.summary}",
    ])


def _slug(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "candidate"


def save_summary(
    summary: QualificationSummary,
    out_dir: Optional[Path] = None,
) -> Path:
    """Write the qualification summary to a JSON file for consultant review."""
    target = Path(out_dir) if out_dir else _SUMMARY_DIR
    target.mkdir(parents=True, exist_ok=True)

    base = _slug(summary.candidate_name)
    path = target / f"{base}.json"
    counter = 2
    while path.exists():
        path = target / f"{base}-{counter}.json"
        counter += 1

    path.write_text(
        json.dumps(
            {"qualification_summary": summary.to_dict()},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path
