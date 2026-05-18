# JD AI Search Agent

## What this is

An AI-powered executive search agent for **JonDavidson Pte Ltd (JD)**, a Singapore-based
executive search firm. The agent automates the **intake-to-longlist** workflow so
consultants can scale candidate outreach and cut time-to-longlist from weeks to days.

The agent is the **third member of JD's Tripartite Search Model**:

- **Lead Consultant** — client engagement, mandate intake, project lead, offer management.
- **Search Consultant** — candidate management, screening, interview arrangement, closure.
- **AI Agent (this build)** — candidate sourcing support, outreach drafting, qualification
  summaries, longlist compilation.

The agent augments consultants; it does not replace human judgement. A consultant
reviews and approves output at each workflow boundary.

## Source of truth

This project is scoped by **`JD_AI_Agent_Developer_Brief_May2026.docx`** (v1.0, May 2026,
prepared by Yvonne, CCO) — kept in this folder. The brief is authoritative for prompts,
JSON schemas, models, compliance rules, and phasing. A related document, Desmond Ong's
`Project_Proposal_AI_Agent_Jondavidson_May2026.pdf`, is referenced by the brief but not
yet in the repo.

## Tech foundation

- **Reasoning engine:** Anthropic Claude API.
  - **Claude Sonnet 4.6** — outreach drafting and qualification/longlist summaries.
  - **Claude Haiku 4.5** — profile data extraction (high-volume, low-cost).
- **Prompt caching:** required. Cache recurring role/search criteria across a mandate
  to cut API cost (brief targets up to ~90% saving on repeated context).
- **Language:** Python 3.9+ (system default is 3.9.6; brief suggests 3.11+ — see PLAN.md).
- **Interface:** command-line tool (CLI). No web UI in v1.
- **Sourcing — LinkedIn RPS (Recruiter Professional Services):** the consultant runs the
  search in LinkedIn RPS and manually exports candidate profiles as **CSV**. The agent
  ingests that CSV. No LinkedIn API, no scraping.
- **Outreach — Dripify:** in this build the consultant sends manually via the Dripify
  dashboard. The agent only **outputs ready-to-send InMail drafts as text files**.
  (Live Dripify webhook integration is a later phase — see roadmap.)

## The 4 workflows (Claude Code prompt framework)

Each workflow is implemented as a callable tool with structured input and JSON output.
Exact system prompts, user-prompt templates, and field schemas are defined in the brief,
Section 5 — build to those.

1. **Intake → Search Criteria** (Sonnet)
   Trigger: consultant submits a new mandate brief.
   Output JSON: `job_titles`, `seniority_levels`, `target_companies`, `industries`,
   `locations`, `boolean_string`, `exclusions`, `search_rationale`.

2. **Personalised InMail Draft** (Sonnet)
   Trigger: a candidate profile is passed in for outreach.
   Output: plain-text InMail, max 150 words, references something specific from the
   profile, never names the client ("our client"), warm peer-to-peer tone, soft CTA.

3. **Candidate Qualification Summary** (Sonnet, with Haiku extraction)
   Trigger: a candidate replies and the message thread is passed in.
   Output JSON: `candidate_name`, `current_role`, `interest_level`, `availability`,
   `location_fit`, `key_positives`, `concerns`, `recommended_action`, `summary`.

4. **Longlist Compilation** (Sonnet)
   Trigger: 15+ candidate qualification summaries collected for a mandate.
   Output JSON: ranked array (`rank`, `candidate_name`, `current_title`,
   `current_company`, `interest_level`, `fit_score` 1–10, `one_line_summary`,
   `recommended_next_step`) plus a `search_commentary` paragraph.

## Build scope — Phase 1A PoC

This build delivers the **Phase 1A proof-of-concept**: the 4 prompts as CLI tools,
driven by **manual input** (CSV in, text files out), tested on one live JD mandate.

**Explicitly out of scope for this build** (later phases per the brief):

- Dripify webhook integration and reply detection (Phase 1B).
- n8n / Make.com workflow orchestration (Phase 1B).
- Google Sheets candidate tracker auto-population (Phase 2).
- Google Drive MCP archiving of longlist documents (Phase 2).
- Multi-user Windows RDS server deployment (Phase 3).

## Compliance & governance

- **PDPA:** candidate data is personal data under Singapore's PDPA. When Drive archiving
  is added, storage must be a **Singapore-based Google Drive** folder. Minimise what is
  stored; candidate CSVs and generated output live in a gitignored `data/` directory.
- **Retention:** archive candidate data after **12 months** unless the candidate is
  actively placed.
- **LinkedIn ToS:** outreach automation is capped at **50 InMails/day** and runs only
  through the dedicated **WangXQ researcher account** — never a consultant's personal
  LinkedIn account.
- **Secrets:** no API keys, credentials, client data, or candidate data committed to
  the repo.

## Design principles

- **Human-in-the-loop:** every workflow ends with consultant review before the next
  begins. No automated outreach without explicit approval.
- **Structured I/O:** workflows pass structured JSON, per the brief's schemas, so each
  stage is inspectable and testable.
- **Prompt caching:** recurring mandate context is cached to control API cost.
- **Adapter boundaries:** LinkedIn RPS (CSV import) and Dripify (text export) sit behind
  interfaces so core logic is testable without external access.
- **Auditability:** record inputs, prompts, and outputs of each run so a consultant can
  trace how a recommendation was reached.

## Status

Plan confirmed and aligned to the developer brief. Building Phase 1A. Step 0 decisions
resolved; the build proceeds phase by phase with a consultant review gate after each.
See PLAN.md.
