"""Thin wrapper around the Anthropic Claude API.

Handles model selection, prompt caching, retries, and JSON parsing so the
workflow modules can stay focused on prompt content.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import anthropic
from dotenv import load_dotenv

# Model roles per the developer brief (Section 3).
MODEL_SONNET = "claude-sonnet-4-6"          # outreach drafting + summaries
MODEL_HAIKU = "claude-haiku-4-5-20251001"   # profile data extraction

# Transient failures worth retrying.
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)
_RETRYABLE_STATUS = {429, 500, 502, 503, 529}

_PLACEHOLDER_KEY = "sk-ant-xxxxxxxx"


class ClaudeError(RuntimeError):
    """Raised when a Claude API call cannot be completed."""


class ClaudeClient:
    """Wraps the Anthropic SDK with retries, prompt caching, and JSON parsing."""

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        load_dotenv()
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key or key == _PLACEHOLDER_KEY:
            raise ClaudeError(
                "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self.max_retries = max(1, max_retries)

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str = MODEL_SONNET,
        max_tokens: int = 2048,
        cache_system: bool = True,
    ) -> str:
        """Send one system+user turn and return Claude's text response.

        When cache_system is True the system prompt is marked for prompt
        caching, so recurring mandate context is billed at the cache rate.
        """
        system_blocks: List[Dict[str, Any]] = [{"type": "text", "text": system}]
        if cache_system:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_blocks,
                    messages=[{"role": "user", "content": user}],
                )
                return "".join(
                    b.text for b in resp.content if b.type == "text"
                ).strip()
            except _RETRYABLE as exc:
                last_error = exc
            except anthropic.APIStatusError as exc:
                if exc.status_code not in _RETRYABLE_STATUS:
                    raise ClaudeError(f"Claude API error: {exc}") from exc
                last_error = exc
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)

        raise ClaudeError(
            f"Claude API call failed after {self.max_retries} attempts: {last_error}"
        ) from last_error

    def complete_json(self, **kwargs: Any) -> Any:
        """Like complete(), but parse the response body as JSON."""
        return extract_json(self.complete(**kwargs))


def extract_json(text: str) -> Any:
    """Parse JSON from a Claude response, tolerating markdown fences/preamble."""
    cleaned = text.strip()

    if cleaned.startswith("```"):
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to the widest { ... } or [ ... ] span in the text.
    starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if not starts or end <= min(starts):
        raise ClaudeError(f"No JSON found in Claude response: {text[:200]}")
    try:
        return json.loads(cleaned[min(starts):end + 1])
    except json.JSONDecodeError as exc:
        raise ClaudeError(f"Could not parse JSON from Claude response: {exc}") from exc
