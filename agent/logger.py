"""Run logger for auditability.

Each workflow run is written as a JSON file under data/runs/ so a consultant
can trace how any recommendation was produced. data/ is gitignored — run logs
contain candidate personal data and must never be committed (PDPA).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_RUNS_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"


def log_run(
    workflow: str,
    model: str,
    inputs: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    output: Any,
    runs_dir: Optional[Path] = None,
) -> Path:
    """Write one run record to disk and return the path to the log file."""
    target = Path(runs_dir) if runs_dir else _RUNS_DIR
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
    }

    safe_workflow = workflow.replace(" ", "_").replace("/", "-")
    path = target / f"{timestamp:%Y%m%d-%H%M%S}_{safe_workflow}.json"
    path.write_text(
        json.dumps(record, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
