"""Pasted LinkedIn Recruiter text → Candidate objects (web-only).

This is the "paste-and-extract" path on the Ranking screen. The consultant
selects the candidates shown on a LinkedIn Recruiter results page, copies them
(plain text), and pastes the block here. We send that text to Claude **Haiku**
— the model the project brief designates for high-volume, low-cost profile
data extraction — and get back a structured list of candidates to rank.

Why this exists:
- It removes the dependency on the Claude *Chrome extension* (a paid, beta,
  per-subscriber feature) for getting candidates into the app. The web app's
  own backend key does the extraction instead, so anyone with the link can use
  it end to end.
- It keeps the original brief's sourcing model intact: the human runs the
  LinkedIn search and copies what's on screen — no API, no scraping.
"""
from __future__ import annotations

from typing import List

from agent.claude_client import MODEL_HAIKU, ClaudeClient
from agent.models import Candidate

# Hard cap so a runaway paste can't blow up the token budget. A Recruiter page
# shows ~25 results; this comfortably covers a few pages pasted at once.
_MAX_CHARS = 60_000

_SYSTEM = (
    "You extract structured candidate records from text a recruiter copied "
    "from a LinkedIn Recruiter search-results page. The text is messy: it may "
    "include navigation, page numbers, 'View profile' links, connection "
    "degrees, and ad copy. Identify each distinct person and pull only their "
    "professional details. Never invent data — if a field isn't present for a "
    "person, leave it empty. Do not include rows that are clearly UI chrome "
    "rather than a real candidate."
)

_USER_TEMPLATE = (
    "Extract every candidate from the text below.\n\n"
    "Return ONLY a JSON array (no prose, no markdown fences). Each element:\n"
    "{\n"
    '  "name": "full name",\n'
    '  "current_title": "current job title / headline",\n'
    '  "current_company": "current employer",\n'
    '  "location": "city / region",\n'
    '  "profile_url": "linkedin url if present, else empty",\n'
    '  "skills": ["skill", ...],\n'
    '  "notes": "any other relevant detail (recent experience, tenure)"\n'
    "}\n\n"
    "If there are no real candidates, return [].\n\n"
    "---- PASTED TEXT ----\n"
    "{pasted}\n"
    "---- END ----"
)


def extract_candidates(text: str, client: ClaudeClient) -> List[Candidate]:
    """Parse pasted Recruiter text into Candidate objects via Claude Haiku."""
    pasted = (text or "").strip()
    if not pasted:
        return []
    if len(pasted) > _MAX_CHARS:
        pasted = pasted[:_MAX_CHARS]

    user = _USER_TEMPLATE.replace("{pasted}", pasted)
    # Budget output for many candidates (~300 tokens each) without truncation.
    max_tokens = max(2048, 1024 + (len(pasted) // 100) * 3)

    raw = client.complete_json(
        system=_SYSTEM,
        user=user,
        model=MODEL_HAIKU,
        max_tokens=max_tokens,
        cache_system=False,  # one-off paste; nothing recurring to cache
    )

    if not isinstance(raw, list):
        return []

    candidates: List[Candidate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        skills_val = item.get("skills") or []
        if isinstance(skills_val, str):
            skills = [s.strip() for s in skills_val.split(",") if s.strip()]
        elif isinstance(skills_val, list):
            skills = [str(s).strip() for s in skills_val if str(s).strip()]
        else:
            skills = []
        notes = str(item.get("notes") or "").strip()
        candidates.append(
            Candidate(
                name=name,
                current_title=str(item.get("current_title") or "").strip(),
                current_company=str(item.get("current_company") or "").strip(),
                location=str(item.get("location") or "").strip(),
                profile_url=str(item.get("profile_url") or "").strip(),
                skills=skills,
                attributes=({"notes": notes} if notes else {}),
            )
        )
    return candidates
