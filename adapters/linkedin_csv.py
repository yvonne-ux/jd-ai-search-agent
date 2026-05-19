"""LinkedIn RPS CSV adapter.

Parses a candidate CSV manually exported from LinkedIn Recruiter Professional
Services into Candidate objects. Header matching is tolerant of the column-name
variations seen across different RPS export formats.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from agent.models import Candidate

# Map each Candidate field to header names that may appear in an RPS export.
# Comparison is lower-cased with surrounding whitespace stripped.
_HEADER_ALIASES: Dict[str, List[str]] = {
    "name": ["name", "full name", "candidate name"],
    "current_title": ["current title", "title", "job title", "position", "headline"],
    "current_company": ["current company", "company", "employer", "organization"],
    "years_in_role": ["years in role", "years in current role", "tenure",
                       "time in role"],
    "prev_company": ["previous company", "prev company", "past company",
                     "former company"],
    "location": ["location", "geography", "region", "city"],
    "skills": ["skills", "key skills", "skill"],
    "profile_url": ["profile url", "linkedin url", "url", "profile", "linkedin"],
}


def _normalize(header: str) -> str:
    return (header or "").strip().lower()


def _split_skills(value: str) -> List[str]:
    # RPS exports separate skills with either commas or semicolons.
    return [s.strip() for s in value.replace(";", ",").split(",") if s.strip()]


def load_candidates(path) -> List[Candidate]:
    """Read an RPS CSV export and return a list of Candidate objects."""
    csv_path = Path(path)
    candidates: List[Candidate] = []

    # utf-8-sig strips the BOM that Excel-saved CSVs often carry.
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return candidates

        norm_to_actual = {
            _normalize(h): h for h in reader.fieldnames if h is not None
        }
        resolved: Dict[str, str] = {}
        for field_name, aliases in _HEADER_ALIASES.items():
            for alias in aliases:
                if alias in norm_to_actual:
                    resolved[field_name] = norm_to_actual[alias]
                    break

        first_header = norm_to_actual.get("first name")
        last_header = norm_to_actual.get("last name")

        # Headers consumed by a core Candidate field (or used to build the
        # name). Every other column is preserved as a named attribute so
        # qualification/experience columns reach the workflows.
        core_headers = set(resolved.values())
        for h in (first_header, last_header):
            if h:
                core_headers.add(h)
        extra_headers = [
            h for h in reader.fieldnames
            if h is not None and h not in core_headers
        ]

        for row in reader:
            def value_of(field_name: str) -> str:
                header = resolved.get(field_name)
                return (row.get(header) or "").strip() if header else ""

            name = value_of("name")
            if not name and (first_header or last_header):
                parts = [
                    (row.get(first_header) or "").strip() if first_header else "",
                    (row.get(last_header) or "").strip() if last_header else "",
                ]
                name = " ".join(p for p in parts if p)

            attributes = {}
            for header in extra_headers:
                cell = (row.get(header) or "").strip()
                if cell:
                    attributes[header.strip()] = cell

            candidates.append(
                Candidate(
                    name=name,
                    current_title=value_of("current_title"),
                    current_company=value_of("current_company"),
                    years_in_role=value_of("years_in_role"),
                    prev_company=value_of("prev_company"),
                    location=value_of("location"),
                    skills=_split_skills(value_of("skills")),
                    profile_url=value_of("profile_url"),
                    attributes=attributes,
                    raw={k: (v or "") for k, v in row.items() if k is not None},
                )
            )

    return candidates
