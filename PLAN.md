# Build Plan — JD AI Search Agent (Phase 1A PoC)

A step-by-step planner for building the AI executive search agent described in
CLAUDE.md, scoped to the **Phase 1A proof-of-concept**.

Each phase lists its goal, the work involved, and what "done" looks like. There is a
consultant review gate at the end of every phase.

## Scope and workflow order

This build delivers **5 workflows as CLI tools driven by manual input**. Four implement
the brief's prompt framework; the fifth (Candidate Ranking) comes from the process map.

**Process order** — how a mandate flows: Intake → Candidate Ranking → InMail →
Qualification → Longlist.

**Build order** — the order steps were implemented below — differs slightly: InMail was
built before Candidate Ranking. This does not affect the runtime flow.

Out of scope (deferred per the brief / process map): Dripify webhooks, n8n/Make.com
orchestration, Stage 5 data sync (RecruitCRM, Google Drive, Gmail), multi-user RDS.

---

## Step 0 — Decisions & access — CONFIRMED

- [x] **Language/runtime:** Python (system 3.9.6; code runs on 3.9+).
- [x] **Interface:** CLI tool. No web UI in v1.
- [x] **LinkedIn RPS access:** manual CSV export.
- [x] **Dripify access:** manual; agent outputs InMail drafts as text files.
- [x] **Storage:** local files; gitignored `data/` directory; 12-month retention.
- [x] **Scope:** Phase 1A PoC — 5 workflows as CLI tools, manual input.
- [x] **Anthropic API key** — in `.env`, verified by a live `check` and `intake` run.

---

## Step 1 — Project scaffold — DONE

Folder structure, dependencies, `.env`/`.gitignore`, README, and a CLI `check`
command. Verified with a live Claude API call.

---

## Step 2 — Shared foundations — DONE

Data models, Claude API wrapper (model selection, prompt caching, retries, JSON
parsing), run logger, LinkedIn RPS CSV adapter, Dripify text-file exporter. Unit-tested.

---

## Step 3 — Workflow 1: Intake → Search Criteria — DONE

Prompt 1 ported; `intake` CLI command turns a mandate brief into structured
`SearchCriteria`. Verified with a live run.

---

## Step 4 — Workflow 3: Personalised InMail Draft — DONE

Prompt 2 ported; `inmail` CLI command drafts a tailored InMail per candidate from an
RPS CSV export, with a word-count / banned-phrase quality check, exported to text files.

---

## Step 5 — Workflow 2: Candidate Ranking — DONE

Ranking prompts authored in the JD house style; `CandidateRanking` model added;
`rank` CLI command scores a CSV against the criteria in one Claude call and flags
the strongest matches. Verified with a live run.

---

## Step 6 — Workflow 4: Candidate Qualification Summary — DONE

Prompt 3 ported; `qualify` CLI command turns a candidate reply thread into a
`QualificationSummary`, with consultant override of the recommended action. Verified
with a live run.

---

## Step 7 — Workflow 5: Longlist Compilation — DONE

Prompt 4 ported; `longlist` CLI command aggregates qualification summaries into a
ranked longlist with market commentary, exported to JSON, Excel, and Markdown.
Verified with a live run.

---

## Step 8 — End-to-end integration — DONE

`pipeline.py` adds per-mandate workspace folders; the `run` command walks all 5
workflows in one guided session with review gates for the RPS search and Dripify
outreach. Verified with a live dry pass.

---

## Step 9 — Hardening & handover — DONE

- [x] Error handling for API failures, rate limits, malformed CSV data (retries in
      the Claude wrapper; CSV loading errors surfaced cleanly in the CLI).
- [x] PDPA review: all generated output and run logs are confined to the gitignored
      `data/` directory; 12-month retention documented in README and CLAUDE.md.
- [x] Cost check: per-call token usage (including prompt-cache reads) is recorded in
      run logs; the `costs` command summarises usage by workflow.
- [x] README finalised as a consultant usage guide covering every command, the
      pipeline, and prompt editing.
- [ ] Pilot with one consultant on a live, low-risk mandate; collect feedback.
      (A human activity — to be scheduled by JD; not a code deliverable.)

---

## Out of scope for this build (deferred per brief / process map)

Dripify webhook / reply detection, n8n / Make.com orchestration, Stage 5 data sync
(RecruitCRM candidate records, Google Drive archiving, Gmail longlist delivery),
multi-user Windows RDS deployment, automated sending, multi-language outreach.

## Build order summary

Step 0 → 1 → 2 → 3 Intake → 4 InMail → 5 Candidate Ranking → 6 Qualification →
7 Longlist → 8 Integration → 9 Hardening — all complete.

The Phase 1A proof-of-concept is built. The remaining activity is a consultant
pilot on a live mandate (Step 9), which JD schedules.
