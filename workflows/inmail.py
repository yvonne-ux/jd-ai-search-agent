"""Workflow 2 — Personalised InMail Draft.

Drafts a tailored LinkedIn InMail for each candidate sourced from a LinkedIn
RPS CSV export. Implements Prompt 2 from the developer brief.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Tuple

from agent.claude_client import MODEL_SONNET, ClaudeClient
from agent.logger import log_run
from agent.models import Candidate
from agent.prompts import fill_template, load_prompt

WORKFLOW = "inmail"
SYSTEM_FILE = "inmail_system.txt"
USER_FILE = "inmail_user.txt"

MAX_WORDS = 150
# Phrases the brief explicitly bans from outreach.
BANNED_PHRASES = ["i came across your profile", "exciting opportunity"]

_NOT_STATED = "(not stated)"


@dataclass
class RoleContext:
    """The role being recruited for, as needed by the InMail prompt."""

    role_title: str = ""
    seniority: str = ""
    role_location: str = ""
    selling_point: str = ""

    @classmethod
    def from_intake_file(cls, path, selling_point: str = "") -> "RoleContext":
        """Build role context from an intake workflow JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        brief = data.get("brief", data)
        return cls(
            role_title=str(brief.get("role_title", "") or "").strip(),
            seniority=str(brief.get("seniority", "") or "").strip(),
            role_location=str(brief.get("location", "") or "").strip(),
            selling_point=selling_point.strip(),
        )


def draft_inmail(
    candidate: Candidate,
    role: RoleContext,
    client: ClaudeClient,
    *,
    max_tokens: int = 512,
) -> str:
    """Run Prompt 2 for one candidate and return the plain-text InMail draft."""
    system = load_prompt(SYSTEM_FILE)
    user = fill_template(
        load_prompt(USER_FILE),
        candidate_name=candidate.name or _NOT_STATED,
        current_title=candidate.current_title or _NOT_STATED,
        current_company=candidate.current_company or _NOT_STATED,
        years_in_role=candidate.years_in_role or _NOT_STATED,
        prev_company=candidate.prev_company or _NOT_STATED,
        location=candidate.location or _NOT_STATED,
        skills=", ".join(candidate.skills) or _NOT_STATED,
        role_title=role.role_title or _NOT_STATED,
        seniority=role.seniority or _NOT_STATED,
        role_location=role.role_location or _NOT_STATED,
        selling_point=role.selling_point or "(none specified)",
    )

    draft = client.complete(
        system=system,
        user=user,
        model=MODEL_SONNET,
        max_tokens=max_tokens,
    )
    log_run(
        WORKFLOW,
        MODEL_SONNET,
        {"candidate": candidate.to_dict(), "role": asdict(role)},
        system,
        user,
        draft,
        usage=client.last_usage,
    )
    return draft


def check_draft(draft: str) -> List[str]:
    """Return a list of quality warnings for a draft (empty means clean)."""
    warnings: List[str] = []

    word_count = len(draft.split())
    if word_count > MAX_WORDS:
        warnings.append(f"{word_count} words — over the {MAX_WORDS}-word limit")

    lowered = draft.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            warnings.append(f'contains discouraged phrase: "{phrase}"')

    return warnings


def draft_all(
    candidates: List[Candidate],
    role: RoleContext,
    client: ClaudeClient,
) -> List[Tuple[Candidate, str, List[str]]]:
    """Draft an InMail for every candidate, with per-draft quality warnings."""
    results: List[Tuple[Candidate, str, List[str]]] = []
    for candidate in candidates:
        draft = draft_inmail(candidate, role, client)
        results.append((candidate, draft, check_draft(draft)))
    return results
