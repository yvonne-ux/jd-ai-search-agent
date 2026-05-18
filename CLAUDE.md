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

This project is scoped by two confidential documents kept in this folder (both
gitignored — local only):

- **`JD_AI_Agent_Developer_Brief_May2026.docx`** (v1.0, May 2026, by Yvonne, CCO) —
  authoritative for the 4 core prompts, JSON schemas, models, compliance, and phasing.
- **`JD_AI_Agent_Process_Map.pdf`** (May 2026) — the intake-to-longlist process map. It
  adds a Stage 2 candidate-ranking step not in the brief's prompt framework, and names
  the Stage 5 systems (RecruitCRM, Google Drive, Gmail).

Desmond Ong's `Project_Proposal_AI_Agent_Jondavidson_May2026.pdf` is referenced by the
brief but not yet in the repo.

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

## The 5 workflows

Each workflow is a callable tool with structured input and JSON output. They are listed
below in process order (the order a mandate flows through them). Workflows 1, 3, 4, and 5
implement the brief's prompt framework (Section 5); workflow 2 comes from the process map.

1. **Intake → Search Criteria** — brief Prompt 1 (Sonnet)
   Trigger: consultant submits a new mandate brief.
   Output JSON: `job_titles`, `seniority_levels`, `target_companies`, `industries`,
   `locations`, `boolean_string`, `exclusions`, `search_rationale`.

2. **Candidate Ranking** — process map, Stage 2 (Sonnet)
   Trigger: consultant exports a candidate CSV from LinkedIn RPS.
   The agent scores each candidate against the role's search criteria and ranks them so
   consultants prioritise outreach to the strongest matches.
   Output JSON: `rankings` array (`rank`, `candidate_name`, `current_title`,
   `current_company`, `fit_score` 1–10, `matches`, `gaps`, `recommendation`).

3. **Personalised InMail Draft** — brief Prompt 2 (Sonnet)
   Trigger: a candidate profile is passed in for outreach.
   Output: plain-text InMail, max 150 words, references something specific from the
   profile, never names the client ("our client"), warm peer-to-peer tone, soft CTA.

4. **Candidate Qualification Summary** — brief Prompt 3 (Sonnet, with Haiku extraction)
   Trigger: a candidate replies and the message thread is passed in.
   Output JSON: `candidate_name`, `current_role`, `interest_level`, `availability`,
   `location_fit`, `key_positives`, `concerns`, `recommended_action`, `summary`.

5. **Longlist Compilation** — brief Prompt 4 (Sonnet)
   Trigger: 15+ candidate qualification summaries collected for a mandate.
   Output JSON: ranked array (`rank`, `candidate_name`, `current_title`,
   `current_company`, `interest_level`, `fit_score` 1–10, `one_line_summary`,
   `recommended_next_step`) plus a `search_commentary` paragraph.

## Build scope — Phase 1A PoC

This build delivers the **Phase 1A proof-of-concept**: the 5 workflows as CLI tools,
driven by **manual input** (CSV in, text files out), tested on one live JD mandate.

**Explicitly out of scope for this build** (later phases per the brief and process map):

- Dripify webhook integration and reply detection (Phase 1B).
- n8n / Make.com workflow orchestration (Phase 1B).
- Stage 5 data sync — RecruitCRM candidate records, Google Drive longlist archiving,
  Gmail delivery of the longlist to the client (Phase 2).
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
