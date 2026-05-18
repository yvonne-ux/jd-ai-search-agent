"""Structured data objects shared across the four workflows.

Field names match the JSON schemas in the developer brief (Section 5) so that
Claude's JSON output maps directly onto these objects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


def _as_str_list(value: Any) -> List[str]:
    """Coerce a JSON value into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(v).strip() for v in value if str(v).strip()]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class SearchCriteria:
    """Output of Workflow 1 — Intake to Search Criteria."""

    job_titles: List[str] = field(default_factory=list)
    seniority_levels: List[str] = field(default_factory=list)
    target_companies: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    boolean_string: str = ""
    exclusions: List[str] = field(default_factory=list)
    search_rationale: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchCriteria":
        return cls(
            job_titles=_as_str_list(data.get("job_titles")),
            seniority_levels=_as_str_list(data.get("seniority_levels")),
            target_companies=_as_str_list(data.get("target_companies")),
            industries=_as_str_list(data.get("industries")),
            locations=_as_str_list(data.get("locations")),
            boolean_string=str(data.get("boolean_string", "") or ""),
            exclusions=_as_str_list(data.get("exclusions")),
            search_rationale=str(data.get("search_rationale", "") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    """A candidate sourced from a LinkedIn RPS CSV export."""

    name: str = ""
    current_title: str = ""
    current_company: str = ""
    years_in_role: str = ""
    prev_company: str = ""
    location: str = ""
    skills: List[str] = field(default_factory=list)
    profile_url: str = ""
    # Any extra columns from the CSV, preserved verbatim.
    raw: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualificationSummary:
    """Output of Workflow 3 — Candidate Qualification Summary."""

    candidate_name: str = ""
    current_role: str = ""
    interest_level: str = ""        # High / Medium / Low / Not Interested
    availability: str = ""          # Actively looking / Open / Not looking / Unknown
    location_fit: str = ""          # Yes / Relocatable / No
    key_positives: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    recommended_action: str = ""    # Progress to call / Hold / Archive
    summary: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualificationSummary":
        return cls(
            candidate_name=str(data.get("candidate_name", "") or ""),
            current_role=str(data.get("current_role", "") or ""),
            interest_level=str(data.get("interest_level", "") or ""),
            availability=str(data.get("availability", "") or ""),
            location_fit=str(data.get("location_fit", "") or ""),
            key_positives=_as_str_list(data.get("key_positives")),
            concerns=_as_str_list(data.get("concerns")),
            recommended_action=str(data.get("recommended_action", "") or ""),
            summary=str(data.get("summary", "") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LonglistEntry:
    """A single ranked entry within a Longlist."""

    rank: int = 0
    candidate_name: str = ""
    current_title: str = ""
    current_company: str = ""
    interest_level: str = ""
    fit_score: int = 0              # 1-10
    one_line_summary: str = ""
    recommended_next_step: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LonglistEntry":
        return cls(
            rank=_as_int(data.get("rank")),
            candidate_name=str(data.get("candidate_name", "") or ""),
            current_title=str(data.get("current_title", "") or ""),
            current_company=str(data.get("current_company", "") or ""),
            interest_level=str(data.get("interest_level", "") or ""),
            fit_score=_as_int(data.get("fit_score")),
            one_line_summary=str(data.get("one_line_summary", "") or ""),
            recommended_next_step=str(data.get("recommended_next_step", "") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Longlist:
    """Output of Workflow 4 — a ranked longlist plus market commentary."""

    entries: List[LonglistEntry] = field(default_factory=list)
    search_commentary: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Longlist":
        # Accept either {"longlist": [...]} or {"entries": [...]}; a bare list
        # is treated as the entries with no commentary.
        if isinstance(data, list):
            rows, commentary = data, ""
        else:
            rows = data.get("longlist") or data.get("entries") or []
            commentary = str(data.get("search_commentary", "") or "")
        return cls(
            entries=[LonglistEntry.from_dict(r) for r in rows],
            search_commentary=commentary,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "longlist": [e.to_dict() for e in self.entries],
            "search_commentary": self.search_commentary,
        }
