"""Run logger and cost summary for auditability.

Each workflow run is written as a JSON file under data/runs/ so a consultant
can trace how any recommendation was produced — including the token usage of
each Claude call. data/ is gitignored: run logs contain candidate personal
data and must never be committed (PDPA).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

RUNS_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"

_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def log_run(
    workflow: str,
    model: str,
    inputs: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    output: Any,
    usage: Optional[Dict[str, int]] = None,
    runs_dir: Optional[Path] = None,
) -> Path:
    """Write one run record to disk and return the path to the log file."""
    target = Path(runs_dir) if runs_dir else RUNS_DIR
    target.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    record = {
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "workflow": workflow,
        "model": model,
        "inputs": inputs,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "output": output,
        "usage": usage or {},
    }

    safe_workflow = workflow.replace(" ", "_").replace("/", "-")
    path = target / f"{timestamp:%Y%m%d-%H%M%S-%f}_{safe_workflow}.json"
    path.write_text(
        json.dumps(record, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _empty_totals() -> Dict[str, int]:
    return {key: 0 for key in _USAGE_KEYS} | {"runs": 0}


def summarize_runs(runs_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Aggregate token usage across all run logs, overall and per workflow."""
    target = Path(runs_dir) if runs_dir else RUNS_DIR
    summary: Dict[str, Any] = {
        "run_count": 0,
        "total": _empty_totals(),
        "by_workflow": {},
    }
    if not target.is_dir():
        return summary

    for path in sorted(target.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        workflow = data.get("workflow", "unknown")
        usage = data.get("usage") or {}
        bucket = summary["by_workflow"].setdefault(workflow, _empty_totals())

        summary["run_count"] += 1
        summary["total"]["runs"] += 1
        bucket["runs"] += 1
        for key in _USAGE_KEYS:
            tokens = int(usage.get(key, 0) or 0)
            summary["total"][key] += tokens
            bucket[key] += tokens

    return summary
