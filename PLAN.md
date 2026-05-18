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

## Step 5 — Workflow 2: Candidate Ranking

(Process map, Stage 2. Runs before InMail in the process flow.)

- [ ] Author the ranking system + user prompts in the JD house style (no brief prompt
      exists for this workflow).
- [ ] Add a `CandidateRanking` data model.
- [ ] Build the workflow: read an RPS CSV, score every candidate against the role's
      `SearchCriteria` in one Claude call, return a ranked list with fit scores,
      matches, gaps, and a Prioritise / Consider / Skip recommendation.
- [ ] Add a `rank` CLI command that displays the ranking and flags top candidates.
- [ ] Consultant review of the ranking before outreach.
- [ ] Test against the sample CSV and sample criteria.

**Done when:** a candidate CSV plus intake criteria produces a sensible ranked list
that a consultant agrees prioritises the right candidates.

---

## Step 6 — Workflow 4: Candidate Qualification Summary

- [ ] Port the brief's Prompt 3 system + user templates into `prompts/`.
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

## Step 7 — Workflow 5: Longlist Compilation

- [ ] Port the brief's Prompt 4 system + user templates into `prompts/`.
- [ ] Aggregate qualification summaries (brief triggers at 15+) into a ranked longlist.
- [ ] Produce the longlist JSON: ranked array (`rank`, `candidate_name`,
      `current_title`, `current_company`, `interest_level`, `fit_score` 1–10,
      `one_line_summary`, `recommended_next_step`) plus a `search_commentary` paragraph.
- [ ] Export a consultant/client-ready document (format to confirm — e.g. Excel).
- [ ] Test a full longlist from the sample candidate set.

**Done when:** a ranked longlist with rationale and search commentary exports correctly
and reads as client-presentable.

---

## Step 8 — End-to-end integration

- [ ] Wire the 5 workflows into one CLI pipeline: brief → criteria → (consultant runs
      RPS search, exports CSV) → ranking → InMail drafts → (consultant sends via
      Dripify, collects replies) → qualification → longlist, with review gates between
      stages.
- [ ] Run a full dry pass on one sample mandate using a sample CSV.

**Done when:** one complete mandate runs end to end on realistic data with consultant
review at each gate.

---

## Step 9 — Hardening & handover

- [ ] Error handling for API failures, rate limits, malformed CSV data.
- [ ] Review PDPA compliance: data minimisation, 12-month retention, `data/` cleanup.
- [ ] Cost check: token usage and prompt-cache hit rate per workflow and per mandate.
- [ ] Finalise README / consultant usage guide so Yvonne can run and adjust prompts
      independently.
- [ ] Pilot with one consultant on a live, low-risk mandate; collect feedback.

**Done when:** a consultant can run a real search with the tool unaided and the data
handling has been reviewed.

---

## Out of scope for this build (deferred per brief / process map)

Dripify webhook / reply detection, n8n / Make.com orchestration, Stage 5 data sync
(RecruitCRM candidate records, Google Drive archiving, Gmail longlist delivery),
multi-user Windows RDS deployment, automated sending, multi-language outreach.

## Build order summary

Step 0 (done) → 1 (done) → 2 (done) → 3 Intake (done) → 4 InMail (done) →
5 Candidate Ranking → 6 Qualification → 7 Longlist → 8 Integration → 9 Hardening.
