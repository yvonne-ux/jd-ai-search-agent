# JD AI Search Agent — Web Interface (v1)

## What this is

A local browser-based UI for the JD AI Search Agent. It runs on the consultant's
own laptop, opens in Safari/Chrome at `http://localhost:5000`, and drives the
existing Python workflows through three linked screens:

1. **Intake** — capture a mandate brief and generate search criteria.
2. **Candidate Ranking** — upload a LinkedIn RPS CSV and view a ranked table.
3. **InMail Drafts** — produce personalised InMail drafts for selected candidates.

The web app is a **thin Flask wrapper** around the existing
`workflows/intake.py`, `workflows/rank.py`, and `workflows/inmail.py` modules —
no business logic is duplicated. Everything that runs in the CLI runs here.

## Scope (v1)

| In scope | Out of scope (deferred) |
| --- | --- |
| Three screens above | Qualify screen |
| Linked mandate flow | Longlist screen |
| Local single-user, no auth | Multi-user / shared deployment |
| Synchronous requests + spinner | Background jobs / progress polling |
| Server-rendered Jinja templates | SPA / React / Vue |
| File-system mandate state | Database-backed mandate state |

Qualify and Longlist remain CLI-only in v1 — they fit a later phase once the
consultant has lived with the three core screens.

## How it relates to the CLI

- The web app **imports the same workflow functions** the CLI uses
  (`from workflows.intake import generate_search_criteria`, etc.).
- Mandates persist under the existing `data/mandates/<slug>/` layout, so a
  consultant can start a mandate in the web UI and finish it in the CLI, or
  vice versa.
- The same prompts under `prompts/` drive both — edit a prompt file and both
  the CLI and the web app pick it up.

## Tech foundation

- **Backend:** Flask (already in Python 3.9.6 ecosystem; no async needed).
- **Templates:** Jinja2 (Flask default), server-rendered HTML.
- **Front end:** plain HTML + CSS + a small amount of vanilla JavaScript —
  enough to drive a loading spinner, an "edit + save" textarea, and a sortable
  table. No framework, no build step.
- **Long Claude calls:** synchronous Flask request. The page shows a centred
  spinner overlay while the request is in flight, then renders the result.
  Adequate for a single-user local app where Claude calls take 5–30 seconds.
- **Branding:** JD navy + teal. Exact hex values to be provided by the user;
  scaffold uses placeholders defined as CSS custom properties so they swap in
  one place.

## Mandate flow (the "linked screens" model)

On entry, the consultant **picks or creates a mandate**. The chosen mandate is
held in a server-side session (Flask's `session` cookie). All three screens
read and write to that mandate's folder under `data/mandates/<slug>/`:

```
data/mandates/<slug>/
    brief.json          (Intake input)
    criteria.json       (Intake output — editable on the Intake screen)
    candidates.csv      (Ranking input — uploaded on the Ranking screen)
    ranking.json        (Ranking output)
    selling_point.txt   (InMail input — entered on the InMail screen)
    inmail_drafts/      (InMail output — editable on the InMail screen)
```

A consultant can switch mandates at any time from the header.

## Editing (a hard requirement)

Every AI output is editable before it leaves the agent:

- **Criteria** — after intake, the search criteria render in a form (job
  titles, target companies, Boolean string, exclusions, etc.). The consultant
  edits and saves before downstream steps.
- **InMail drafts** — each draft renders in a textarea, character/word count
  visible, "Save" persists the edit to disk.

The agent is the third member of the Tripartite Search Model; the consultant
keeps the final word at every step.

## Compliance & governance (carried over from the parent project)

- All mandate artefacts live under `data/mandates/`, which is **gitignored**.
- No client data, candidate data, or generated drafts go into the repo.
- `.env` (Anthropic key) is gitignored.
- LinkedIn outreach is still capped at **50 InMails/day** via the WangXQ
  account — the web UI shows this reminder on the InMail screen, exactly as
  the CLI does.

## Design principles

- **Thin server, fat workflows.** Routes are 20-line handlers; everything
  reusable stays in `workflows/`.
- **No JavaScript framework.** Vanilla JS, progressively enhanced HTML forms.
  If a route works without JS, it has to keep working without JS.
- **One mandate at a time.** No tabs, no parallel mandates in v1 — the
  consultant picks one mandate and works it through.
- **Same source of truth as the CLI.** The web app never invents its own
  storage layout or its own prompt copies.

## Status

Plan stage. No code yet — `PLAN.md` lays out the build order.
