# Build Plan — JD AI Search Agent (Phase 1A PoC)

A step-by-step planner for building the AI executive search agent described in
CLAUDE.md, scoped to the **Phase 1A proof-of-concept** from the developer brief
(`JD_AI_Agent_Developer_Brief_May2026.docx`).

Each phase lists its goal, the work involved, and what "done" looks like. Phases are
ordered so each one is testable before the next begins. There is a consultant review
gate at the end of every phase.

## How this maps to the brief's phases

- The brief's **Phase 1A** (Weeks 1–2) = Prompts 1–2 live, manual input.
- The brief's **Phase 1B** (Weeks 3–4) = Prompts 3–4 + Dripify integration.

This build delivers **all 4 prompts as CLI tools driven by manual input** — i.e. Phase
1A plus the manual (non-automated) portions of Phase 1B. The automation layers — Dripify
webhooks, n8n/Make.com, Google Sheets, Google Drive MCP, RDS — are **out of scope** and
deferred to brief Phases 1B/2/3.

---

## Step 0 — Decisions & access — CONFIRMED

All blockers resolved (confirmed by consultant):

- [x] **Language/runtime:** Python (system default 3.9.6; brief suggests 3.11+ — code
      written to run on 3.9+; upgrade optional).
- [x] **Interface:** CLI tool. No web UI in v1.
- [x] **LinkedIn RPS access:** manual **CSV export** — consultant exports candidate
      profiles from RPS and feeds the CSV into the tool. No API, no scraping.
- [x] **Dripify access:** manual — consultant sends from the Dripify dashboard. The
      agent only **outputs ready-to-send InMail drafts as text files**.
- [x] **Storage:** local files for v1. Candidate CSVs and output live in a gitignored
      `data/` directory. 12-month retention per the brief.
- [x] **Scope:** Phase 1A PoC — 4 prompts as CLI tools, manual input. Automation layers
      deferred.
- [ ] **Anthropic API key** — obtained and placed in `.env` (not committed). Done at
      Step 1 setup.

---

## Step 1 — Project scaffold

- [ ] Create folder structure (`/agent` core logic, `/adapters`, `/prompts`,
      `/workflows`, `/tests`, `/data` gitignored).
- [ ] `requirements.txt` (anthropic SDK, python-dotenv).
- [ ] `.env.example` and `.gitignore` (ignore `.env`, `/data`, caches).
- [ ] `README.md` with setup and run instructions, written so Yvonne can run, monitor,
      and adjust prompts independently (a brief deliverable).
- [ ] CLI entry point (`main.py`) with a `check` command that makes a minimal
      "hello Claude" API call.
- [ ] Verify the Claude API call works end to end once the key is in `.env`.

**Done when:** repo runs, `python main.py check` returns a successful Claude response.

---

## Step 2 — Shared foundations

- [ ] Define structured data objects matching the brief's JSON schemas:
      `SearchCriteria`, `Candidate`, `QualificationSummary`, `LonglistEntry`.
- [ ] Build a thin Claude API wrapper: model selection (Sonnet 4.6 for drafting/
      summaries, Haiku 4.5 for extraction), prompt loading, JSON response parsing,
      retry/error handling.
- [ ] Implement **prompt caching** for recurring mandate/role context (brief deliverable
      — targets up to ~90% cost saving on repeated context).
- [ ] Build a run logger for auditability (inputs, prompt, output per run).
- [ ] Build the **LinkedIn RPS CSV adapter**: parse an exported RPS CSV into a list of
      `Candidate` objects (tolerant of column-name variations).
- [ ] Build the **Dripify text-file exporter**: write InMail drafts to plain `.txt`
      files in `data/`, one per candidate, ready to copy into Dripify.

**Done when:** data models, Claude wrapper, prompt caching, logger, CSV adapter, and
text exporter exist and are unit-tested against a sample CSV.

---

## Step 3 — Prompt 1: Intake → Search Criteria

- [ ] Port the brief's Prompt 1 system prompt and user-prompt template into `/prompts`.
- [ ] CLI command to collect a mandate brief (client, role, industry, location,
      seniority, responsibilities, must-have, nice-to-have, exclusions).
- [ ] Produce the `SearchCriteria` JSON: `job_titles`, `seniority_levels`,
      `target_companies`, `industries`, `locations`, `boolean_string`, `exclusions`,
      `search_rationale`.
- [ ] Consultant review/edit step before criteria are accepted.
- [ ] Test against 2–3 sample briefs from real past JD mandates.

**Done when:** a sample brief produces accurate, consultant-approved search criteria,
including a ready-to-paste LinkedIn RPS Boolean string.

---

## Step 4 — Prompt 2: Personalised InMail Draft

- [ ] Port the brief's Prompt 2 system prompt and user-prompt template into `/prompts`.
- [ ] Ingest a LinkedIn RPS CSV export via the Step 2 adapter.
- [ ] Draft a tailored InMail per candidate: max 150 words, references a specific
      profile detail, never names the client, warm peer-to-peer tone, soft CTA, no
      banned phrases ("I came across your profile", "exciting opportunity").
- [ ] Write each draft to a `.txt` file via the Dripify exporter; every draft is
      consultant-editable before sending.
- [ ] Test drafts for personalisation quality and tone.

**Done when:** a CSV of candidates produces one consultant-ready `.txt` InMail draft per
candidate, ready to copy into Dripify.

---

## Step 5 — Prompt 3: Candidate Qualification Summary

- [ ] Port the brief's Prompt 3 system prompt and user-prompt template into `/prompts`.
- [ ] CLI input for a candidate's LinkedIn message thread (consultant pastes the thread).
- [ ] Produce the `QualificationSummary` JSON: `candidate_name`, `current_role`,
      `interest_level`, `availability`, `location_fit`, `key_positives`, `concerns`,
      `recommended_action`, `summary`.
- [ ] Use Haiku 4.5 for profile extraction where applicable, Sonnet 4.6 for the summary.
- [ ] Consultant override of `recommended_action`.
- [ ] Test against sample threads spanning strong / borderline / weak fit.

**Done when:** qualification output is consistent and a consultant agrees with the
recommended actions on the test set.

---

## Step 6 — Prompt 4: Longlist Compilation

- [ ] Port the brief's Prompt 4 system prompt and user-prompt template into `/prompts`.
- [ ] Aggregate qualification summaries (brief triggers at 15+) into a ranked longlist.
- [ ] Produce the longlist JSON: ranked array (`rank`, `candidate_name`,
      `current_title`, `current_company`, `interest_level`, `fit_score` 1–10,
      `one_line_summary`, `recommended_next_step`) plus a `search_commentary` paragraph.
- [ ] Export a consultant/client-ready document (format to confirm — e.g. Excel).
- [ ] Test a full longlist from the sample candidate set.

**Done when:** a ranked longlist with rationale and search commentary exports correctly
and reads as client-presentable.

---

## Step 7 — End-to-end integration

- [ ] Wire the 4 prompts into one CLI pipeline: brief → criteria → (consultant runs RPS
      search, exports CSV) → InMail drafts → (consultant sends via Dripify, collects
      replies) → qualification → longlist, with review gates between stages.
- [ ] Run a full dry pass on one sample mandate using a sample CSV.

**Done when:** one complete mandate runs end to end on realistic data with consultant
review at each gate.

---

## Step 8 — Hardening & handover

- [ ] Error handling for API failures, rate limits, malformed CSV data.
- [ ] Review PDPA compliance: data minimisation, 12-month retention, `data/` cleanup.
- [ ] Cost check: token usage and prompt-cache hit rate per workflow and per mandate.
- [ ] Finalise README / consultant usage guide so Yvonne can run and adjust prompts
      independently.
- [ ] Pilot with one consultant on a live, low-risk mandate; collect feedback.

**Done when:** a consultant can run a real search with the tool unaided and the data
handling has been reviewed.

---

## Out of scope for this build (deferred per brief)

Dripify webhook / reply detection, n8n / Make.com orchestration, Google Sheets tracker
auto-population, Google Drive MCP archiving, multi-user Windows RDS deployment,
automated sending, multi-language outreach. Revisit per brief Phases 1B / 2 / 3.

## Build order summary

Step 0 (done) → 1 (scaffold) → 2 (foundations + caching) → 3 (Intake) → 4 (InMail) →
5 (Qualification) → 6 (Longlist) → 7 (Integration) → 8 (Hardening).
