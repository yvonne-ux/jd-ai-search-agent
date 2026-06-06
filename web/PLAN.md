# Build Plan — JD AI Search Agent Web Interface (v1)

A step-by-step planner for the local Flask UI scoped in `web/CLAUDE.md`.

Each step ends with a **live test gate**: the consultant opens the app in
Safari/Chrome, exercises the new screen, and says "continue to Step N" before
the next step begins. Same gating model as the CLI build.

---

## Step 0 — Decisions confirmed

- [x] **Location:** `web/` subfolder inside `jd-ai-search-agent/`.
- [x] **Screen flow:** linked — one mandate flows through all three screens.
- [x] **Brand colours:** JD navy + teal. **Exact hex values pending** — to be
      pasted by user; scaffold uses placeholders.
- [x] **Long-call UX:** synchronous request + spinner overlay.
- [x] **Auth:** none (local single-user).
- [x] **Scope:** three screens — Intake, Ranking, InMail. Qualify and Longlist
      stay CLI-only in v1.

---

## Step 1 — Flask scaffold + brand chrome

**Goal:** a runnable Flask app that opens to a landing page, lets the
consultant pick or create a mandate, and shows the JD-branded header on every
page.

**Work:**
- `web/app.py` — Flask app factory, session cookie config, route stubs.
- `web/templates/base.html` — `<header>` with JD navy bar, app title, current
  mandate name, "Switch mandate" link.
- `web/templates/mandates.html` — list existing mandates from
  `data/mandates/`, "Create new mandate" form (name + slug).
- `web/static/style.css` — colour custom properties (`--jd-navy`, `--jd-teal`,
  …), header/typography, spinner overlay, basic form & table styles.
- `web/static/app.js` — show/hide spinner on form submit; nothing else.
- `web/requirements.txt` (or extend root `requirements.txt`) — `flask`,
  `python-dotenv` (already in root).
- `web/README.md` — one-page "how to run the web app" guide.

**Done when:**
- `python web/app.py` launches and Safari opens to `http://localhost:5000`.
- The landing page lists current mandates and lets the user create one.
- The header is JD-branded (placeholder hex values, swap-ready).
- Switching mandates updates the header.

**Live test gate.**

---

## Step 2 — Intake screen

**Goal:** capture a mandate brief, generate search criteria via the existing
`workflows.intake`, render the result as an editable form, save edits.

**Work:**
- `web/templates/intake.html`:
  - Form with the nine `BRIEF_FIELDS` from `workflows/intake.py`.
  - Free-text fields render as textareas; list fields (responsibilities,
    must_have, nice_to_have, exclusions) accept one-per-line input.
- Route `POST /intake/generate` → calls `generate_search_criteria()`, saves
  `criteria.json` under the current mandate, redirects to the criteria view.
- `web/templates/criteria.html`:
  - Renders the criteria as an editable form (chips/lists for job titles,
    target companies, etc.; full-width textarea for the Boolean string).
  - "Save criteria" persists edits back to `criteria.json`.
- Spinner overlay during the Claude call.

**Done when:**
- A consultant fills in the brief, clicks Generate, sees the same criteria the
  CLI would produce.
- The consultant can edit any field (e.g. tweak the Boolean string) and save.
- The mandate folder now contains `brief.json` + `criteria.json`.

**Live test gate.**

---

## Step 3 — Candidate Ranking screen

**Goal:** upload a LinkedIn RPS CSV, score it against the current mandate's
criteria via `workflows.rank`, render a ranked table with verdicts.

**Work:**
- `web/templates/rank.html`:
  - "Upload candidates CSV" file picker (multipart form).
  - Shows current criteria summary (read-only) so the consultant knows what
    they are ranking against.
- Route `POST /rank/run` →
  - Saves uploaded CSV as `candidates.csv` under the mandate.
  - Calls `load_candidates()` + `rank_candidates()`.
  - Saves `ranking.json`.
- `web/templates/ranking_table.html`:
  - Sortable HTML table — rank, name, current title, current company, fit
    score, recommendation, matches, gaps.
  - "Prioritise" rows highlighted with the JD-teal accent.
  - Checkbox per row + "Draft InMails for selected" button that takes the
    selection to the InMail screen.
- Spinner overlay during the Claude call.

**Done when:**
- A consultant uploads the demo CSV and sees a ranked table in the browser.
- Rows display the experience attributes flowing through from the adapter
  (Siemens NX yrs, aerospace yrs, CNC yrs).
- Selecting a few rows and clicking "Draft InMails" navigates to the InMail
  screen with those candidates pre-selected.

**Live test gate.**

---

## Step 4 — InMail Drafts screen

**Goal:** generate personalised InMail drafts for the selected candidates,
edit them in the browser, save the edits.

**Work:**
- `web/templates/inmail.html`:
  - Pre-filled list of selected candidates (carried over from Ranking).
  - "Selling point" textarea (single-line OK) — pre-fills from
    `selling_point.txt` if previously saved.
  - "Generate drafts" button.
- Route `POST /inmail/generate` → calls `draft_all()` for the selected
  candidates, writes each draft as a `.txt` file under
  `<mandate>/inmail_drafts/`.
- `web/templates/inmail_drafts.html`:
  - One block per draft: candidate name header, editable `<textarea>` with
    the draft text, live word counter, "Save" button, "Copy to clipboard"
    button.
  - The 150-word cap shows as a warning when exceeded (mirrors the CLI's
    `check_draft`).
  - LinkedIn cap reminder ("Max 50 InMails/day via WangXQ") in a small note.
- Spinner overlay during the Claude call.

**Done when:**
- A consultant selects three candidates on the Ranking screen, lands on the
  InMail screen with them listed, types a selling point, clicks Generate, and
  sees three editable drafts in the browser.
- Edits persist to disk.
- The drafts appear under `data/mandates/<slug>/inmail_drafts/` exactly as if
  the CLI had produced them.

**Live test gate.**

---

## Step 5 — Polish & handover

**Goal:** make the app feel finished and ready for the consultant pilot.

**Work:**
- Friendly error pages (missing key, malformed CSV, Claude failure).
- JD branding refinement once the user pastes the actual hex values.
- A short consultant guide in `web/README.md` (start the app, walk one
  mandate end-to-end, where files live).
- Smoke tests using Flask's test client (`web/tests/test_routes.py`) —
  routes return 200, forms render, mandate creation works. The Claude-calling
  routes are tested with the workflow functions monkey-patched out, so the
  test suite doesn't hit the API.
- No PDPA changes — `data/mandates/` is already gitignored.

**Done when:**
- A consultant can walk a real mandate end-to-end in the browser, no CLI use,
  without help.
- `python -m unittest discover web/tests` passes.

**Live test gate.**

---

## Out of scope for v1

- Qualify and Longlist screens (CLI-only in v1).
- Authentication / multi-user / hosted deployment.
- Background jobs, progress bars, server-sent events.
- React / Vue / any SPA framework.
- Database — file system remains the source of truth.

## Open question for Step 1

**Exact hex codes for JD navy and JD teal** — paste them before Step 1 starts
and they go straight into `web/static/style.css`. If you don't have them yet,
I'll scaffold with placeholders and we swap later in Step 5.
