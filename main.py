"""JD AI Search Agent — CLI entry point.

See CLAUDE.md for project context and PLAN.md for the build plan.

Commands:
  check    Verify the Anthropic API connection.
  intake   Workflow 1 — turn a mandate brief into LinkedIn search criteria.
  rank     Workflow 2 — score and rank candidates against the role criteria.
  inmail   Workflow 3 — draft personalised InMails for a list of candidates.
  qualify  Workflow 4 — qualify a candidate from their reply thread.
  longlist Workflow 5 — compile qualified candidates into a ranked longlist.
  run      Guided end-to-end run of all 5 workflows for one mandate.
  costs    Summarise Claude API token usage across all logged runs.
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


def _load_candidates(path: str):
    """Load candidates from a CSV. Returns (candidates, error_message)."""
    import csv
    from pathlib import Path

    from adapters.linkedin_csv import load_candidates

    csv_path = Path(path)
    if not csv_path.exists():
        return None, f"candidate CSV not found: {csv_path}"
    try:
        candidates = load_candidates(csv_path)
    except (OSError, ValueError, csv.Error) as exc:
        return None, f"could not read candidate CSV: {exc}"
    if not candidates:
        return None, "no candidates found in the CSV."
    return candidates, None


def cmd_rank(args: argparse.Namespace) -> int:
    """Workflow 2 — score and rank candidates against the role criteria."""
    from pathlib import Path

    from agent.claude_client import ClaudeClient, ClaudeError
    from workflows.rank import (
        format_rankings,
        load_criteria_from_intake,
        rank_candidates,
        save_rankings,
    )

    candidates, error = _load_candidates(args.candidates)
    if error:
        print(f"ERROR: {error}")
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
    """Workflow 3 — draft personalised InMails for a list of candidates."""
    from pathlib import Path

    from adapters.dripify_export import export_inmail
    from agent.claude_client import ClaudeClient, ClaudeError
    from workflows.inmail import RoleContext, draft_all

    candidates, error = _load_candidates(args.candidates)
    if error:
        print(f"ERROR: {error}")
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


def cmd_longlist(args: argparse.Namespace) -> int:
    """Workflow 5 — compile qualified candidates into a ranked longlist."""
    from pathlib import Path

    from agent.claude_client import ClaudeClient, ClaudeError
    from workflows.longlist import (
        MIN_SUMMARIES,
        LonglistContext,
        compile_longlist,
        format_longlist,
        load_qualification_summaries,
        save_longlist,
    )

    summaries = load_qualification_summaries(args.summaries)
    if not summaries:
        print(f"ERROR: no qualification summaries found in {args.summaries}")
        return 1
    if len(summaries) < MIN_SUMMARIES:
        print(
            f"Note: {len(summaries)} summary(ies) found — the brief compiles a "
            f"longlist at {MIN_SUMMARIES}+. Proceeding anyway."
        )

    criteria_path = Path(args.criteria)
    if not criteria_path.exists():
        print(f"ERROR: criteria file not found: {criteria_path}")
        return 1
    try:
        context = LonglistContext.from_intake_file(criteria_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: could not read criteria file: {exc}")
        return 1

    try:
        client = ClaudeClient()
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"\nCompiling a longlist from {len(summaries)} summary(ies)...\n")
    try:
        longlist = compile_longlist(summaries, context, client)
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("=" * 60)
    print(format_longlist(longlist))
    print("=" * 60 + "\n")

    out_dir = Path(args.out_dir) if args.out_dir else None
    paths = save_longlist(longlist, context, criteria_path.stem, out_dir)
    print(f"Saved JSON:     {paths['json']}")
    print(f"Saved Markdown: {paths['markdown']}")
    print(f"Saved Excel:    {paths['excel']}")
    return 0


def _stage_banner(title: str) -> None:
    print("\n" + "-" * 60)
    print(title)
    print("-" * 60)


def cmd_run(args: argparse.Namespace) -> int:
    """Guided end-to-end run of all 5 workflows for one mandate."""
    from pathlib import Path

    from adapters.dripify_export import export_inmail
    from agent.claude_client import ClaudeClient, ClaudeError
    from workflows.intake import (
        format_criteria,
        generate_search_criteria,
        save_criteria,
    )
    from workflows.inmail import RoleContext, draft_all
    from workflows.longlist import (
        LonglistContext,
        compile_longlist,
        format_longlist,
        load_qualification_summaries,
        save_longlist,
    )
    from workflows.pipeline import create_mandate
    from workflows.qualify import (
        QualifyContext,
        format_summary,
        qualify_candidate,
        save_summary,
    )
    from workflows.rank import format_rankings, rank_candidates, save_rankings

    try:
        client = ClaudeClient()
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    try:
        # --- Stage 1: Intake -------------------------------------------------
        _stage_banner("Stage 1 — Intake & brief")
        brief = _collect_brief_interactive()
        if not brief.role_title:
            print("ERROR: a role title is required.")
            return 1

        print("\nGenerating search criteria...")
        criteria = generate_search_criteria(brief, client)
        print("\n" + format_criteria(criteria) + "\n")

        mandate_name = f"{brief.client_name} {brief.role_title}".strip()
        mandate = create_mandate(mandate_name or brief.role_title)
        save_criteria(criteria, brief, out_dir=mandate.folder)
        print(f"Mandate workspace: {mandate.folder}")

        # --- Gate: LinkedIn RPS search --------------------------------------
        _stage_banner("GATE — LinkedIn RPS candidate search")
        print("Run the search in LinkedIn RPS using this Boolean string:\n")
        print(f"  {criteria.boolean_string}\n")
        print("Export the matching candidates as a CSV file.")
        csv_in = input("Path to the candidate CSV (blank to stop here): ").strip()
        if not csv_in:
            print(f"\nStopped after intake. Resume later with: rank --criteria "
                  f"<the saved criteria> --candidates <your CSV>")
            return 0
        candidates, error = _load_candidates(csv_in)
        if error:
            print(f"ERROR: {error}")
            return 1

        # --- Stage 2: Candidate ranking -------------------------------------
        _stage_banner("Stage 2 — Candidate ranking")
        print(f"Ranking {len(candidates)} candidate(s)...\n")
        rankings = rank_candidates(candidates, criteria, client)
        print(format_rankings(rankings))
        save_rankings(rankings, "ranking", out_dir=mandate.folder)

        priority_names = {
            r.candidate_name.strip().lower()
            for r in rankings
            if r.recommendation.lower() == "prioritise"
        }
        choice = input(
            "\nDraft InMails for [a]ll candidates or [p]rioritised only? [p]: "
        ).strip().lower()
        if choice == "a" or not priority_names:
            targets = candidates
        else:
            targets = [
                c for c in candidates
                if c.name.strip().lower() in priority_names
            ] or candidates

        # --- Stage 3: Personalised outreach ---------------------------------
        _stage_banner("Stage 3 — Personalised InMail drafting")
        selling_point = input("One key selling point for outreach: ").strip()
        role = RoleContext(
            role_title=brief.role_title,
            seniority=brief.seniority,
            role_location=brief.location,
            selling_point=selling_point,
        )
        print(f"\nDrafting InMails for {len(targets)} candidate(s)...\n")
        for candidate, draft, warnings in draft_all(targets, role, client):
            path = export_inmail(candidate.name, draft, mandate.inmail_dir)
            print(f"  {candidate.name or 'Unknown'} -> {path}")
            for warning in warnings:
                print(f"    WARNING: {warning}")

        # --- Gate: Dripify outreach -----------------------------------------
        _stage_banner("GATE — Dripify outreach & replies")
        print("Send the drafts via Dripify (WangXQ account, max 50 InMails/day).")
        print("As candidates reply, provide each reply thread to qualify them.")

        client_type = brief.industry or brief.client_name
        qualify_context = QualifyContext(
            role_title=brief.role_title,
            client_type=client_type,
            location=brief.location,
            must_have=brief.must_have,
        )
        qualified_any = False
        while True:
            thread_in = input(
                "Path to a reply thread file (blank to finish): "
            ).strip()
            if not thread_in:
                break
            thread_path = Path(thread_in)
            if not thread_path.exists():
                print(f"  not found: {thread_path}")
                continue
            thread = thread_path.read_text(encoding="utf-8")

            _stage_banner("Stage 4 — Candidate qualification")
            summary = qualify_candidate(thread, qualify_context, client)
            print(format_summary(summary))
            save_summary(summary, out_dir=mandate.qualifications_dir)
            qualified_any = True

        if not qualified_any:
            print("\nNo replies qualified yet. Run 'longlist' later once "
                  "qualification summaries have been collected.")
            print(f"Mandate workspace: {mandate.folder}")
            return 0

        # --- Stage 5: Longlist ----------------------------------------------
        _stage_banner("Stage 5 — Longlist compilation")
        summaries = load_qualification_summaries(mandate.qualifications_dir)
        longlist_context = LonglistContext(
            role_title=brief.role_title,
            client_type=client_type,
            location=brief.location,
            must_have=brief.must_have,
        )
        print(f"Compiling a longlist from {len(summaries)} summary(ies)...\n")
        longlist = compile_longlist(summaries, longlist_context, client)
        print(format_longlist(longlist))
        paths = save_longlist(
            longlist, longlist_context, "longlist", out_dir=mandate.folder
        )
        print(f"\nSaved JSON:     {paths['json']}")
        print(f"Saved Markdown: {paths['markdown']}")
        print(f"Saved Excel:    {paths['excel']}")
    except ClaudeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"\nMandate complete. All artifacts in: {mandate.folder}")
    return 0


def cmd_costs(args: argparse.Namespace) -> int:
    """Summarise Claude API token usage across all logged runs."""
    from agent.logger import summarize_runs

    summary = summarize_runs()
    if summary["run_count"] == 0:
        print("No run logs found yet. Run a workflow first.")
        return 0

    print(f"Workflow runs logged: {summary['run_count']}\n")
    row = "{:<12} {:>5} {:>11} {:>11} {:>11} {:>11}"
    header = row.format(
        "Workflow", "Runs", "Input", "Output", "CacheRead", "CacheWrite"
    )
    print(header)
    print("-" * len(header))
    for workflow, totals in sorted(summary["by_workflow"].items()):
        print(row.format(
            workflow[:12],
            totals["runs"],
            totals["input_tokens"],
            totals["output_tokens"],
            totals["cache_read_input_tokens"],
            totals["cache_creation_input_tokens"],
        ))
    total = summary["total"]
    print("-" * len(header))
    print(row.format(
        "TOTAL",
        total["runs"],
        total["input_tokens"],
        total["output_tokens"],
        total["cache_read_input_tokens"],
        total["cache_creation_input_tokens"],
    ))

    cached = total["cache_read_input_tokens"]
    cacheable = cached + total["input_tokens"]
    if cacheable:
        print(
            f"\nPrompt-cache read rate: {100 * cached / cacheable:.1f}% "
            f"of cacheable input tokens."
        )
    print("\nToken counts above drive API cost — see console.anthropic.com "
          "for current per-model pricing.")
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

    longlist = sub.add_parser(
        "longlist",
        help="Workflow 5 — compile qualified candidates into a ranked longlist.",
    )
    longlist.add_argument(
        "--summaries",
        metavar="DIR",
        default="data/qualifications",
        help="Directory of qualification summary JSON files "
             "(default: data/qualifications).",
    )
    longlist.add_argument(
        "--criteria",
        metavar="PATH",
        required=True,
        help="Intake criteria JSON for the role.",
    )
    longlist.add_argument(
        "--out-dir",
        metavar="PATH",
        help="Directory for the longlist files (default: data/longlists).",
    )

    sub.add_parser(
        "run",
        help="Guided end-to-end run of all 5 workflows for one mandate.",
    )

    sub.add_parser(
        "costs",
        help="Summarise Claude API token usage across all logged runs.",
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
    if args.command == "longlist":
        return cmd_longlist(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "costs":
        return cmd_costs(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
