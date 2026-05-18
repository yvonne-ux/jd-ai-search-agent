"""Prompt template loading and filling.

Prompt text lives in the prompts/ directory as plain files so a consultant can
adjust wording without touching Python code.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def load_prompt(name: str) -> str:
    """Load a prompt template by filename from the prompts/ directory."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def fill_template(template: str, **values: Any) -> str:
    """Replace {{key}} placeholders with the given values.

    A placeholder with no matching value is left untouched, so a missing field
    is visible in the output rather than silently blank.
    """
    def replace(match: "re.Match[str]") -> str:
        key = match.group(1)
        return str(values[key]) if key in values else match.group(0)

    return _PLACEHOLDER.sub(replace, template)
