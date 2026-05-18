"""JD AI Search Agent — CLI entry point.

See CLAUDE.md for project context and PLAN.md for the build plan.

Commands:
  check    Verify the Anthropic API connection.
  intake   Workflow 1 — turn a mandate brief into LinkedIn search criteria.
  rank     Workflow 2 — score and rank candidates against the role criteria.
  inmail   Workflow 3 — draft personalised InMails for a list of candidates.
  qualify  Workflow 4 — qualify a candidate from their reply thread.
"""
from __future__ import annotations

import argparse
import json
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


def _collect_brief_interactive():
    """Prompt the consultant for each mandate brief field."""
    from workflows.intake import BRIEF_FIELDS, MandateBrief

    print("Enter the mandate brief. Press Enter to leave a field blank.\n")
    values = {}
    for field, label in BRIEF_FIELDS:
        values[field] = input(f"  {label}: ").strip()
    return MandateBrief.from_dict(values)


def cmd_intake(args: argparse.Namespace) -> int:
    """Workflow 1 — generate search criteria from a mandate brief."""
    from workflows.intake import (
        MandateBrief,
        format_criteria,
        generate_search_criteria,
        save_criteria,
    )
    from agent.claude_client import ClaudeClient, ClaudeError

    if args.from_file:
        try:
            data = json.loads(open(args.from_file, encoding="utf-8").read())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: could not read brief file: {exc}")
            return 1
        # Accept either a bare brief or the {"brief": {...}} wrapper.
        brief = MandateBrief.from_dict(data.get("brief", data))
    else:
        brief = _collect_brief_interactive()

    if not brief.role_title:
        print("ERROR: a role title is required.")
        return 1

    try:
        client = ClaudeClient()
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\nGenerating search criteria...")
    try:
        criteria = generate_search_criteria(brief, client)
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\n" + "=" * 60)
    print(format_criteria(criteria))
    print("=" * 60 + "\n")

    if not args.from_file:
        answer = input("Save these criteria? [Y/n]: ").strip().lower()
        if answer == "n":
            print("Discarded — nothing saved.")
            return 0

    path = save_criteria(criteria, brief)
    print(f"Saved to {path}")
    print("Review and edit that JSON file before running the LinkedIn RPS search.")
    return 0


def cmd_rank(args: argparse.Namespace) -> int:
    """Workflow 2 — score and rank candidates against the role criteria."""
    from pathlib import Path

    from adapters.linkedin_csv import load_candidates
    from agent.claude_client import ClaudeClient, ClaudeError
    from workflows.rank import (
        format_rankings,
        load_criteria_from_intake,
        rank_candidates,
        save_rankings,
    )

    csv_path = Path(args.candidates)
    if not csv_path.exists():
        print(f"ERROR: candidate CSV not found: {csv_path}")
        return 1
    candidates = load_candidates(csv_path)
    if not candidates:
        print("ERROR: no candidates found in the CSV.")
        return 1

    criteria_path = Path(args.criteria)
    if not criteria_path.exists():
        print(f"ERROR: criteria file not found: {criteria_path}")
        return 1
    try:
        criteria = load_criteria_from_intake(criteria_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: could not read criteria file: {exc}")
        return 1

    try:
        client = ClaudeClient()
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"\nRanking {len(candidates)} candidate(s) against the role criteria...\n")
    try:
        rankings = rank_candidates(candidates, criteria, client)
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("=" * 60)
    print(format_rankings(rankings))
    print("=" * 60 + "\n")

    if args.top:
        priority = rankings[:args.top]
    else:
        priority = [
            r for r in rankings if r.recommendation.lower() == "prioritise"
        ]
    if priority:
        names = ", ".join(r.candidate_name or "Unknown" for r in priority)
        print(f"Prioritise for outreach: {names}")

    out_dir = Path(args.out_dir) if args.out_dir else None
    path = save_rankings(rankings, criteria_path.stem, out_dir)
    print(f"Saved ranking to {path}")
    return 0


def cmd_inmail(args: argparse.Namespace) -> int:
    """Workflow 2 — draft personalised InMails for a list of candidates."""
    from pathlib import Path

    from adapters.dripify_export import export_inmail
    from adapters.linkedin_csv import load_candidates
    from agent.claude_client import ClaudeClient, ClaudeError
    from workflows.inmail import RoleContext, draft_all

    csv_path = Path(args.candidates)
    if not csv_path.exists():
        print(f"ERROR: candidate CSV not found: {csv_path}")
        return 1
    candidates = load_candidates(csv_path)
    if not candidates:
        print("ERROR: no candidates found in the CSV.")
        return 1

    if args.criteria:
        try:
            role = RoleContext.from_intake_file(args.criteria)
        except (OSError, ValueError) as exc:
            print(f"ERROR: could not read criteria file: {exc}")
            return 1
    else:
        print("Enter the role details:")
        role = RoleContext(
            role_title=input("  Role title: ").strip(),
            seniority=input("  Seniority: ").strip(),
            role_location=input("  Location: ").strip(),
        )

    if not role.role_title:
        print("ERROR: a role title is required.")
        return 1

    role.selling_point = (
        args.selling_point
        or input("One key selling point for outreach: ").strip()
    )

    try:
        client = ClaudeClient()
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"\nDrafting InMails for {len(candidates)} candidate(s)...\n")
    try:
        results = draft_all(candidates, role, client)
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else None
    for candidate, draft, warnings in results:
        path = export_inmail(candidate.name, draft, out_dir)
        print(f"  {candidate.name or 'Unknown'} -> {path}")
        for warning in warnings:
            print(f"    WARNING: {warning}")

    print(f"\n{len(results)} draft(s) written. Review and edit each before sending.")
    print("Reminder: cap LinkedIn outreach at 50 InMails/day via the WangXQ account.")
    return 0


def _read_thread_interactive() -> str:
    """Collect a pasted message thread, ending on a line containing only END."""
    print("Paste the LinkedIn message thread, then a line containing only END:")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def cmd_qualify(args: argparse.Namespace) -> int:
    """Workflow 4 — qualify a candidate from their reply thread."""
    from pathlib import Path

    from agent.claude_client import ClaudeClient, ClaudeError
    from workflows.qualify import (
        QualifyContext,
        format_summary,
        normalize_action,
        qualify_candidate,
        save_summary,
    )

    if args.thread:
        thread_path = Path(args.thread)
        if not thread_path.exists():
            print(f"ERROR: thread file not found: {thread_path}")
            return 1
        thread = thread_path.read_text(encoding="utf-8")
    else:
        thread = _read_thread_interactive()
    if not thread.strip():
        print("ERROR: the message thread is empty.")
        return 1

    if args.criteria:
        try:
            context = QualifyContext.from_intake_file(args.criteria)
        except (OSError, ValueError) as exc:
            print(f"ERROR: could not read criteria file: {exc}")
            return 1
    else:
        print("Enter the role details:")
        context = QualifyContext(
            role_title=input("  Role title: ").strip(),
            client_type=input("  Client type (industry/sector): ").strip(),
            location=input("  Location: ").strip(),
            must_have=input("  Must-have background: ").strip(),
        )

    if not context.role_title:
        print("ERROR: a role title is required.")
        return 1

    try:
        client = ClaudeClient()
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\nGenerating qualification summary...")
    try:
        summary = qualify_candidate(thread, context, client)
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("\n" + "=" * 60)
    print(format_summary(summary))
    print("=" * 60 + "\n")

    try:
        answer = input(
            "Accept recommended action? [Y] or type Progress / Hold / Archive: "
        ).strip()
    except EOFError:
        answer = ""
    if answer and answer.lower() not in ("y", "yes"):
        mapped = normalize_action(answer)
        if mapped:
            summary.recommended_action = mapped
            print(f"Action overridden to: {mapped}")
        else:
            print(
                f"Unrecognised action '{answer}' — "
                f"keeping '{summary.recommended_action}'."
            )

    path = save_summary(summary)
    print(f"Saved to {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jd-ai-search-agent",
        description="AI executive search agent for JonDavidson Pte Ltd.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Verify the Anthropic API connection.")

    intake = sub.add_parser(
        "intake",
        help="Workflow 1 — turn a mandate brief into LinkedIn search criteria.",
    )
    intake.add_argument(
        "--from-file",
        metavar="PATH",
        help="Read the mandate brief from a JSON file instead of prompting.",
    )

    rank = sub.add_parser(
        "rank",
        help="Workflow 2 — score and rank candidates against the role criteria.",
    )
    rank.add_argument(
        "--candidates",
        metavar="PATH",
        required=True,
        help="LinkedIn RPS CSV export of candidates to rank.",
    )
    rank.add_argument(
        "--criteria",
        metavar="PATH",
        required=True,
        help="Intake criteria JSON for the role.",
    )
    rank.add_argument(
        "--top",
        metavar="N",
        type=int,
        help="Flag the top N candidates (default: those recommended Prioritise).",
    )
    rank.add_argument(
        "--out-dir",
        metavar="PATH",
        help="Directory for the ranking JSON (default: data/rankings).",
    )

    inmail = sub.add_parser(
        "inmail",
        help="Workflow 3 — draft personalised InMails for a list of candidates.",
    )
    inmail.add_argument(
        "--candidates",
        metavar="PATH",
        required=True,
        help="LinkedIn RPS CSV export of candidates to draft InMails for.",
    )
    inmail.add_argument(
        "--criteria",
        metavar="PATH",
        help="Intake criteria JSON for the role; if omitted, role is prompted.",
    )
    inmail.add_argument(
        "--selling-point",
        metavar="TEXT",
        help="One key selling point for the outreach; prompted if omitted.",
    )
    inmail.add_argument(
        "--out-dir",
        metavar="PATH",
        help="Directory for the draft .txt files (default: data/inmail_drafts).",
    )

    qualify = sub.add_parser(
        "qualify",
        help="Workflow 4 — qualify a candidate from their reply thread.",
    )
    qualify.add_argument(
        "--thread",
        metavar="PATH",
        help="Text file with the message thread; pasted interactively if omitted.",
    )
    qualify.add_argument(
        "--criteria",
        metavar="PATH",
        help="Intake criteria JSON for role context; prompted if omitted.",
    )
    return parser


def main(argv: "list[str] | None" = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check()
    if args.command == "intake":
        return cmd_intake(args)
    if args.command == "rank":
        return cmd_rank(args)
    if args.command == "inmail":
        return cmd_inmail(args)
    if args.command == "qualify":
        return cmd_qualify(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
