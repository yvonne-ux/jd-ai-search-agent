"""JD file → MandateBrief extraction (web-only).

Pure-Python, no Claude call. Reads a PDF or DOCX uploaded on the Intake screen
and produces a populated :class:`workflows.intake.MandateBrief` plus the set of
field names the agent was confident enough to pre-fill (used by the template
to show the "FROM JD" indicator).

Why heuristics instead of an LLM call here:
- The consultant always reviews and edits the brief on the same screen — the
  agent's job at this step is to save typing, not to be authoritative.
- It keeps Intake instant (no spinner) and runs offline, so a consultant can
  pre-load briefs without burning API tokens.
- The downstream Prompt 1 (Sonnet) still does the real work of converting the
  reviewed brief into structured SearchCriteria.
"""
from __future__ import annotations

import io
import re
from dataclasses import asdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from workflows.intake import BRIEF_FIELDS, MandateBrief

# ---------------------------------------------------------------------------
# Skill / signal libraries used to identify must- vs nice-to-have content.
# Kept in sync with the equivalent list in web/step1.html.
# ---------------------------------------------------------------------------

_SKILL_LIB: Tuple[str, ...] = (
    # languages
    "Python", "Java", "Scala", "Go", "Golang", "C#", "C++", "TypeScript",
    "JavaScript", "Ruby", "Rust", "Kotlin", "Swift", "PHP", "R",
    "SQL", "T-SQL", "PL/SQL",
    # data / warehouses
    "Spark", "PySpark", "Hadoop", "Airflow", "dbt", "Kafka", "Flink", "Beam",
    "Databricks", "Snowflake", "BigQuery", "Redshift", "Synapse",
    "Data Warehouse", "Data Lake", "Lakehouse", "Delta Lake",
    # cloud
    "AWS", "GCP", "Azure", "EKS", "ECS", "EMR", "Glue", "Lambda",
    "S3", "Athena", "Kinesis", "Cloud Run", "Dataflow", "Dataproc",
    # infra
    "Terraform", "Kubernetes", "Docker", "Helm", "Ansible", "Pulumi",
    "CI/CD", "GitHub Actions", "GitLab CI", "Jenkins",
    # backend
    "Node.js", "Express", "Django", "FastAPI", "Flask", "Spring",
    "Spring Boot", "gRPC", "GraphQL", "REST",
    # frontend
    "React", "Next.js", "Vue", "Angular", "Svelte", "Tailwind",
    # databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "DynamoDB", "Cassandra", "ClickHouse",
    # ml / ai
    "PyTorch", "TensorFlow", "scikit-learn", "HuggingFace", "LangChain",
    "LLM", "RAG", "NLP", "Computer Vision",
    # role-y
    "Leadership", "Mentoring", "Stakeholder", "Architecture",
    "System Design", "Microservices", "Event-driven",
)

_INDUSTRY_LIB: Tuple[str, ...] = (
    "Banking", "Financial Services", "FSI", "Fintech", "Insurance",
    "Wealth Management", "Asset Management", "Capital Markets",
    "Healthcare", "Pharmaceuticals", "Biotech",
    "Retail", "E-commerce", "Logistics", "Supply Chain",
    "Gaming", "Media", "Telecommunications",
    "SaaS", "Enterprise Software", "Cybersecurity",
    "Manufacturing", "Energy", "Oil & Gas",
    "Government", "Public Sector", "Education",
)

_CITIES: Tuple[str, ...] = (
    "Singapore", "Kuala Lumpur", "Penang", "Johor Bahru",
    "Hong Kong", "Shanghai", "Beijing", "Shenzhen", "Taipei",
    "Tokyo", "Osaka", "Sydney", "Melbourne", "Auckland",
    "Bangkok", "Jakarta", "Manila", "Ho Chi Minh", "Hanoi",
    "Mumbai", "Bengaluru", "Bangalore", "Delhi", "Chennai", "Hyderabad",
    "London", "Dubai", "New York", "San Francisco", "Remote",
)


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------

class ExtractError(Exception):
    """Raised when a JD file can't be read into plain text."""


def _read_pdf(blob: bytes) -> str:
    """Pull text from each PDF page in order. Scanned PDFs come back empty."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover — surfaced via the route
        raise ExtractError("PDF support unavailable — install `pypdf`.") from exc
    try:
        reader = PdfReader(io.BytesIO(blob))
    except Exception as exc:
        raise ExtractError(f"Couldn't open this PDF ({exc}).") from exc
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            # One bad page shouldn't kill the whole upload.
            continue
    return "\n\n".join(parts)


def _read_docx(blob: bytes) -> str:
    """Concatenate paragraph text from a .docx file."""
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise ExtractError("DOCX support unavailable — install `python-docx`.") from exc
    try:
        doc = Document(io.BytesIO(blob))
    except Exception as exc:
        raise ExtractError(f"Couldn't open this Word document ({exc}).") from exc
    return "\n".join(p.text for p in doc.paragraphs)


def _read_plain(blob: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return blob.decode(enc)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="ignore")


def read_jd_file(filename: str, blob: bytes) -> str:
    """Dispatch on filename and return cleaned plain text."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        raw = _read_pdf(blob)
    elif name.endswith((".docx", ".doc")):
        raw = _read_docx(blob)
    elif name.endswith((".txt", ".md")):
        raw = _read_plain(blob)
    else:
        # Best-effort: try PDF magic first, then DOCX (zip), then plain.
        if blob[:4] == b"%PDF":
            raw = _read_pdf(blob)
        elif blob[:2] == b"PK":
            raw = _read_docx(blob)
        else:
            raw = _read_plain(blob)
    cleaned = _clean(raw)
    if len(cleaned) < 40:
        raise ExtractError(
            "Couldn't read meaningful text from the file. "
            "If this is a scanned PDF, run OCR first."
        )
    return cleaned


def _clean(raw: str) -> str:
    text = raw.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Field-level extractors. Each returns a string (or empty) — the orchestrator
# decides which fields to mark as "FROM JD".
# ---------------------------------------------------------------------------

def _labelled(text: str, label_pattern: str) -> Optional[str]:
    """Find a line like ``Label: value`` and return ``value`` (trimmed).

    The label must start a line (``(?:^|\n)`` anchor) and the value must live
    on the SAME line — we use ``[ \\t]*`` between the separator and the capture
    so a newline doesn't silently pull text off the next line (which used to
    cause section headings to be returned as field values).
    """
    pat = rf"(?:^|\n)[ \t]*(?:{label_pattern})[ \t]*[:\-–][ \t]*([^\n]{{2,200}})"
    m = re.search(pat, text, flags=re.IGNORECASE)
    if not m:
        return None
    value = m.group(1).strip().rstrip(".")
    return value or None


# Phrases that look title-y but are actually section headers / boilerplate.
# Anything in this set is rejected as a role-title candidate.
_NOT_A_TITLE: Tuple[str, ...] = (
    "general knowledge", "specialised knowledge", "specialized knowledge",
    "job description", "job summary", "job specification", "job purpose",
    "role description", "role summary", "role purpose", "role requirements",
    "position description", "position summary", "position purpose",
    "the role", "the position", "about the role", "about the position",
    "about the company", "about us", "about the client", "background",
    "overview", "key requirements", "key responsibilities", "key areas",
    "responsibilities", "requirements", "qualifications", "skills",
    "experience", "confidential", "confidential search",
    "job title", "role title", "position title", "save", "apply",
    "fire life safety", "hygiene & food safety", "hygiene and food safety",
    "operations", "staffing and training", "marketing & planning",
    "marketing and planning", "administration", "administration and other duties",
)

# Words that strongly suggest a real job title.
_TITLE_HINTS = re.compile(
    r"\b("
    r"engineer|developer|architect|designer|analyst|scientist|"
    r"manager|director|officer|head|lead|principal|chief|"
    r"senior|junior|specialist|associate|consultant|executive|"
    r"coordinator|administrator|supervisor|"
    r"chef|sommelier|sous|sommelier|"
    r"president|founder|partner|advisor|controller|accountant|auditor|"
    r"counsel|attorney|paralegal|nurse|doctor|therapist|technician|operator|"
    r"agent|broker|trader|recruiter|sourcer|writer|editor|producer|teacher|professor|"
    r"intern|trainee|apprentice|fellow|vp|cto|cio|cfo|coo|ceo"
    r")\b",
    flags=re.IGNORECASE,
)


def _looks_like_title(line: str) -> bool:
    """Heuristic: does this line look like a real job title?"""
    if not line:
        return False
    norm = re.sub(r"[^a-z0-9& ]+", " ", line.lower()).strip()
    norm = re.sub(r"\s+", " ", norm)
    if norm in _NOT_A_TITLE:
        return False
    # Must contain at least one strong role keyword to count as a title.
    return bool(_TITLE_HINTS.search(line))


def _extract_role_title(text: str) -> str:
    # 1) Labelled line — "Job Title: …" or "Position: …" on its own line.
    found = _labelled(text, r"job\s*title|role\s*title|position\s*title|position|role")
    if found:
        candidate = found.strip().rstrip(".:;,")
        # Strip trailing location / status suffixes that often appear after
        # the title on the same line (e.g. "F&B Director — Manila (on-site)").
        candidate = re.split(
            r"\s+[-–—|]\s+(?:confidential|manila|singapore|hong\s*kong|"
            r"hybrid|remote|on[\s-]*site)\b",
            candidate, maxsplit=1, flags=re.IGNORECASE,
        )[0].strip()
        if candidate and candidate.lower() not in _NOT_A_TITLE and _looks_like_title(candidate):
            return candidate
        # Labelled value didn't look like a real title — fall through.

    # 2) Fallback: scan the first ~12 non-empty lines for one that LOOKS like
    #    a real job title (contains a strong role keyword and isn't a section
    #    header).
    seen = 0
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        seen += 1
        if seen > 12:
            break
        if not (4 < len(line) < 80):
            continue
        if line[0:1].islower():
            continue
        if re.search(r"[.!?]\s", line):
            continue
        if not _looks_like_title(line):
            continue
        return re.sub(
            r"\s*[-–—|]\s*confidential\b.*", "", line, flags=re.IGNORECASE
        ).strip()
    return ""


def _extract_client(text: str) -> str:
    found = _labelled(text, r"client(?:\s*name)?|company|employer|organi[sz]ation")
    if found:
        return found
    if re.search(r"\bconfidential\b", text[:600], flags=re.IGNORECASE):
        return "Confidential"
    return ""


def _extract_industry(text: str) -> str:
    found = _labelled(text, r"industry|sector|vertical")
    if found:
        return found
    head = text[:3000]
    for industry in _INDUSTRY_LIB:
        if re.search(rf"\b{re.escape(industry)}\b", head, flags=re.IGNORECASE):
            return industry
    return ""


def _extract_location(text: str) -> str:
    found = _labelled(text, r"location|based\s*in|work\s*location|site|country")
    if found:
        return found
    for city in _CITIES:
        if re.search(rf"\b{re.escape(city)}\b", text, flags=re.IGNORECASE):
            suffix = ""
            if re.search(r"\bhybrid\b", text, flags=re.IGNORECASE):
                suffix = " (hybrid)"
            elif re.search(r"\bremote\b", text, flags=re.IGNORECASE):
                suffix = " (remote)"
            elif re.search(r"\bon[\s-]*site\b", text, flags=re.IGNORECASE):
                suffix = " (on-site)"
            return city + suffix
    return ""


# Seniority output is normalised to the same vocabulary the Level/Seniority
# <select> renders, so the dropdown shows a matched option whenever possible.
SENIORITY_VOCAB: Tuple[str, ...] = (
    "Junior",
    "Mid-level",
    "Senior",
    "Senior / Lead",
    "Lead / Staff",
    "Director / Principal",
    "Head / VP",
    "C-Suite",
)


def _normalise_seniority(raw: str) -> str:
    """Map a free-text seniority value into the controlled dropdown vocab."""
    lc = (raw or "").lower()
    if not lc:
        return ""
    if re.search(r"c-?suite|chief|\bcto\b|\bcio\b|\bcfo\b|\bcoo\b", lc):
        return "C-Suite"
    if re.search(r"head\s+of|\bvp\b|vice\s+president", lc):
        return "Head / VP"
    if "director" in lc or "principal" in lc:
        return "Director / Principal"
    if "staff" in lc:
        return "Lead / Staff"
    if "lead" in lc:
        return "Senior / Lead" if "senior" in lc else "Lead / Staff"
    if "senior" in lc or "sr." in lc:
        return "Senior"
    if "mid" in lc or "intermediate" in lc:
        return "Mid-level"
    if re.search(r"junior|jr\.|entry|graduate", lc):
        return "Junior"
    # Fall back to the original text capitalised so the dropdown still shows
    # something meaningful even if it isn't a perfect match.
    return raw.strip().title()


def _extract_seniority(text: str) -> str:
    found = _labelled(text, r"seniority|level|grade")
    if found:
        return _normalise_seniority(found)
    head = text[:1500].lower()
    if re.search(r"\b(chief|cto|cio|cfo|coo)\b", head):
        return "C-Suite"
    if re.search(r"\b(head of|vp\b|vice president)\b", head):
        return "Head / VP"
    if re.search(r"\b(director|principal)\b", head):
        return "Director / Principal"
    if re.search(r"\b(lead|staff)\b", head) and re.search(r"\bsenior\b", head):
        return "Senior / Lead"
    if re.search(r"\b(lead|staff)\b", head):
        return "Lead / Staff"
    if re.search(r"\b(senior|sr\.)\b", head):
        return "Senior"
    if re.search(r"\b(mid|intermediate)\b", head):
        return "Mid-level"
    if re.search(r"\b(junior|jr\.|entry)\b", head):
        return "Junior"
    return ""


def _slice_section(text: str, heading_alts: Iterable[str]) -> str:
    """Return the body of a section whose heading matches any alt.

    A "heading" is a short line followed by content; the section ends at the
    next plausible heading (a Title-Case line under ~40 chars) or end-of-text.
    """
    alts = "|".join(heading_alts)
    pat = (
        rf"(?:^|\n)\s*(?:{alts})\s*[:\-–]?\s*\n+"
        r"([\s\S]+?)"
        r"(?=\n\s*[A-Z][A-Za-z &/]{3,40}\s*[:\-–]?\s*\n|$)"
    )
    m = re.search(pat, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _bulletise(section: str, *, limit: int = 12) -> List[str]:
    """Turn a slice of JD prose into clean per-line bullets."""
    if not section:
        return []
    items: List[str] = []
    for raw_line in section.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Strip leading bullets / numbering.
        line = re.sub(r"^[\-\*•●◦·▪▫■□]+\s*", "", line)
        line = re.sub(r"^\(?\d+[.)]\s+", "", line)
        line = re.sub(r"^[a-z][.)]\s+", "", line)
        if len(line) < 4:
            continue
        items.append(line.rstrip("."))
        if len(items) >= limit:
            break
    return items


def _extract_responsibilities(text: str) -> str:
    section = _slice_section(text, [
        r"key\s+responsibilities",
        r"responsibilities",
        r"role\s+responsibilities",
        r"what\s+you'?ll\s+do",
        r"duties",
        r"the\s+role",
    ])
    bullets = _bulletise(section, limit=10)
    return "\n".join(bullets)


def _extract_must_have(text: str) -> str:
    section = _slice_section(text, [
        r"must[- ]haves?",
        r"required\s+skills",
        r"requirements",
        r"key\s+requirements",
        r"minimum\s+qualifications",
        r"essential\s+skills",
        r"core\s+skills",
        r"what\s+we'?re\s+looking\s+for",
    ])
    bullets = _bulletise(section, limit=10)
    if bullets:
        return "\n".join(bullets)
    # Fall back: pull any matching skills from the entire JD.
    hits = _match_skills(text, _SKILL_LIB)
    return "\n".join(hits[:8])


def _extract_nice_to_have(text: str) -> str:
    section = _slice_section(text, [
        r"nice[- ]to[- ]haves?",
        r"preferred(?:\s+qualifications)?",
        r"bonus",
        r"good\s+to\s+have",
        r"desirable",
        r"advantageous",
        r"plus",
    ])
    bullets = _bulletise(section, limit=8)
    return "\n".join(bullets)


def _extract_exclusions(text: str) -> str:
    section = _slice_section(text, [
        r"exclusions?",
        r"do\s+not\s+consider",
        r"will\s+not\s+consider",
        r"not\s+open\s+to",
    ])
    bullets = _bulletise(section, limit=6)
    if bullets:
        return "\n".join(bullets)
    # Lightweight signal fallback from JD body.
    signals = []
    if re.search(r"contractor[\s-]?only|contract\s+only", text, flags=re.IGNORECASE):
        signals.append("Contractor-only profiles")
    if re.search(r"\b(?:on[\s-]*site\s+only|no\s+remote)\b", text, flags=re.IGNORECASE):
        signals.append("On-site-only profiles")
    if re.search(r"\b(?:junior\s+only|<\s*[234]\s*yrs?)\b", text, flags=re.IGNORECASE):
        signals.append("Junior or < 4 yrs experience")
    return "\n".join(signals)


def _match_skills(section: str, lib: Iterable[str]) -> List[str]:
    """Case-insensitive, whole-token skill match (preserves library casing)."""
    if not section:
        return []
    found: List[str] = []
    seen: Set[str] = set()
    for skill in lib:
        # `(?<![A-Za-z0-9])` works as a word boundary that also handles `C++`.
        pat = rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])"
        if re.search(pat, section, flags=re.IGNORECASE) and skill not in seen:
            found.append(skill)
            seen.add(skill)
    return found


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_brief(text: str, existing: Optional[MandateBrief] = None) -> Tuple[MandateBrief, Set[str]]:
    """Run all field extractors against ``text``.

    Returns the new brief and the set of field names that came from the JD
    (the template uses this set to render the "FROM JD" dot). If ``existing``
    is provided, only blank fields are filled — the consultant's typed values
    are never overwritten.
    """
    existing = existing or MandateBrief()
    base: Dict[str, str] = asdict(existing)

    extractors = {
        "client_name":      _extract_client(text),
        "role_title":       _extract_role_title(text),
        "industry":         _extract_industry(text),
        "location":         _extract_location(text),
        "seniority":        _extract_seniority(text),
        "responsibilities": _extract_responsibilities(text),
        "must_have":        _extract_must_have(text),
        "nice_to_have":     _extract_nice_to_have(text),
        "exclusions":       _extract_exclusions(text),
    }

    extracted_fields: Set[str] = set()
    for field, _label in BRIEF_FIELDS:
        candidate = extractors.get(field, "").strip()
        if not candidate:
            continue
        if base.get(field, "").strip():
            # User already filled this — don't clobber, don't claim it.
            continue
        base[field] = candidate
        extracted_fields.add(field)

    return MandateBrief.from_dict(base), extracted_fields


def field_completeness(brief: MandateBrief) -> Tuple[int, int]:
    """Return (filled, total) across the brief fields."""
    filled = sum(
        1 for field, _ in BRIEF_FIELDS
        if str(getattr(brief, field, "") or "").strip()
    )
    return filled, len(BRIEF_FIELDS)
