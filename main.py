"""JD AI Search Agent — CLI entry point.

Phase 1A scaffold. See CLAUDE.md for project context and PLAN.md for the build plan.

Commands:
  check   Verify the Anthropic API connection.
"""
from __future__ import annotations

import argparse
import os
import sys

# Haiku is used only for the lightweight connectivity check.
CHECK_MODEL = "claude-haiku-4-5-20251001"


def cmd_check() -> int:
    """Make a minimal Claude API call to verify connectivity and credentials."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv not installed. Run: pip install -r requirements.txt")
        return 1
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key == "sk-ant-xxxxxxxx":
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("Copy .env.example to .env and paste your key from console.anthropic.com.")
        return 1

    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic SDK not installed. Run: pip install -r requirements.txt")
        return 1

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=CHECK_MODEL,
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": "Reply with exactly this sentence: JD AI Search Agent connected.",
            }],
        )
    except Exception as exc:
        print("ERROR: Claude API call failed.")
        print(f"  {type(exc).__name__}: {exc}")
        return 1

    reply = "".join(b.text for b in resp.content if b.type == "text").strip()
    print(f"OK — Claude ({CHECK_MODEL}) responded:")
    print(f"  {reply}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jd-ai-search-agent",
        description="AI executive search agent for JonDavidson Pte Ltd.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check", help="Verify the Anthropic API connection.")
    return parser


def main(argv: "list[str] | None" = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
