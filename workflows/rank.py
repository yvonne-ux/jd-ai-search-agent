"""Workflow 2 — Candidate Ranking.

Scores and ranks a list of candidates from a LinkedIn RPS CSV export against a
role's search criteria, so consultants can prioritise outreach to the strongest
matches. Sourced from the intake-to-longlist process map (Stage 2).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from agent.claude_client import MODEL_SONNET, ClaudeClient
from agent.logger import log_run
from agent.models import Candidate, CandidateRanking, SearchCriteria
from agent.prompts import fill_template, load_prompt

WORKFLOW = "rank"
SYSTEM_FILE = "rank_system.txt"
USER_FILE = "rank_user.txt"

_RANKINGS_DIR = Path(__file__).resolve().parent.parent / "data" / "rankings"


def load_criteria_from_intake(path) -> SearchCriteria:
    """Load SearchCriteria from an intake workflow JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return SearchCriteria.from_dict(data.get("search_criteria", data))


def _candidate_payload(candidate: Candidate) -> dict:
    return {
        "name": candidate.name,
        "current_title": candidate.current_title,
        "current_company": candidate.current_company,
        "years_in_role": candidate.years_in_role,
        "prev_company": candidate.prev_company,
        "location": candidate.location,
        "skills": candidate.skills,
        "attributes": candidate.attributes,
    }


def rank_candidates(
    candidates: List[Candidate],
    criteria: SearchCriteria,
    client: ClaudeClient,
    *,
    max_tokens: int = 0,
) -> List[CandidateRanking]:
    """Score every candidate against the criteria and return a ranked list."""
    # The model emits one JSON object per candidate (~700 tokens each). Size the
    # output budget to the batch so large CSVs are not truncated mid-response.
    if max_tokens <= 0:
        max_tokens = max(4096, 1024 + len(candidates) * 700)
    system = load_prompt(SYSTEM_FILE)
    user = fill_template(
        load_prompt(USER_FILE),
        criteria=json.dumps(criteria.to_dict(), indent=2, ensure_ascii=False),
        candidate_count=str(len(candidates)),
        candidates=json.dumps(
            [_candidate_payload(c) for c in candidates],
            indent=2,
            ensure_ascii=False,
        ),
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
        {"criteria": criteria.to_dict(), "candidate_count": len(candidates)},
        system,
        user,
        raw,
        usage=client.last_usage,
    )

    rows = raw.get("rankings", []) if isinstance(raw, dict) else raw
    rankings = [CandidateRanking.from_dict(row) for row in rows]
    # Re-sort by fit score and renumber, so rank is always consistent.
    rankings.sort(key=lambda r: r.fit_score, reverse=True)
    for position, ranking in enumerate(rankings, 1):
        ranking.rank = position
    return rankings


def format_rankings(rankings: List[CandidateRanking]) -> str:
    """Render the ranked list as a readable block for consultant review."""
    if not rankings:
        return "(no candidates ranked)"

    lines: List[str] = []
    for ranking in rankings:
        title = ", ".join(
            part for part in [ranking.current_title, ranking.current_company] if part
        )
        header = f"#{ranking.rank}  {ranking.candidate_name or 'Unknown'}"
        if title:
            header += f" — {title}"
        lines.append(header)
        lines.append(
            f"    Fit {ranking.fit_score}/10 · {ranking.recommendation or 'n/a'}"
        )
        if ranking.matches:
            lines.append("    Matches: " + "; ".join(ranking.matches))
        if ranking.gaps:
            lines.append("    Gaps: " + "; ".join(ranking.gaps))
        lines.append("")
    return "\n".join(lines).rstrip()


def _slug(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "ranking"


def save_rankings(
    rankings: List[CandidateRanking],
    name: str,
    out_dir: Optional[Path] = None,
) -> Path:
    """Write the ranked list to a JSON file the consultant can review."""
    target = Path(out_dir) if out_dir else _RANKINGS_DIR
    target.mkdir(parents=True, exist_ok=True)

    base = _slug(name)
    path = target / f"{base}.json"
    counter = 2
    while path.exists():
        path = target / f"{base}-{counter}.json"
        counter += 1

    path.write_text(
        json.dumps(
            {"rankings": [r.to_dict() for r in rankings]},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path
