# JD AI Search Agent

An AI-powered executive search agent for **JonDavidson Pte Ltd** that automates the
intake-to-longlist workflow. It is a command-line tool built on the Anthropic Claude
API. See `CLAUDE.md` for full project context and `PLAN.md` for the build plan.

## What it does

The agent runs five workflows, in the order a mandate flows through them:

1. **Intake → Search Criteria** — turns a client brief into LinkedIn search criteria,
   including a ready-to-paste Boolean string.
2. **Candidate Ranking** — scores and ranks a candidate CSV against the role criteria.
3. **Personalised InMail Draft** — drafts a tailored InMail per candidate.
4. **Candidate Qualification** — assesses a candidate's reply into a structured summary.
5. **Longlist Compilation** — aggregates qualified candidates into a ranked longlist.

A consultant reviews and approves the output at each stage. The agent does not connect
to LinkedIn or Dripify directly — candidate CSVs go in, draft text files come out.

## Requirements

- Python 3.9 or newer
- An Anthropic API key — generate one at https://console.anthropic.com/

## Setup

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Add your API key:

   ```bash
   cp .env.example .env
   ```

   Open `.env` and paste your key after `ANTHROPIC_API_KEY=`. **Never commit `.env`** —
   it is gitignored.

4. Verify the setup:

   ```bash
   python main.py check
   ```

## Usage

### Guided end-to-end run

The simplest way to run a full mandate. It walks all five workflows, pausing at two
gates for the manual steps (the LinkedIn RPS search and the Dripify outreach):

```bash
python main.py run
```

All artifacts for the mandate are saved together under `data/mandates/<name>/`.

### Individual workflows

Each workflow can also be run on its own — useful for resuming a mandate or re-running
one stage:

```bash
# 1. Intake — generate search criteria from a brief
python main.py intake                          # interactive
python main.py intake --from-file brief.json   # from a JSON brief

# 2. Ranking — score a candidate CSV against the criteria
python main.py rank --candidates candidates.csv --criteria <criteria.json>

# 3. InMail — draft personalised InMails
python main.py inmail --candidates candidates.csv --criteria <criteria.json> \
    --selling-point "One key selling point"

# 4. Qualification — assess a candidate's reply
python main.py qualify --thread reply.txt --criteria <criteria.json>

# 5. Longlist — compile qualified candidates
python main.py longlist --criteria <criteria.json>
```

### Monitoring API cost

```bash
python main.py costs
```

Summarises Claude token usage (including prompt-cache reads) across every logged run.

## Editing the prompts

Every prompt lives in `prompts/` as a plain text file — `<workflow>_system.txt` and
`<workflow>_user.txt`. They can be edited directly, with no code changes. Placeholders
in the user prompts use `{{double_braces}}` and are filled in by the workflow.

## Project layout

```
jd-ai-search-agent/
├── main.py        CLI entry point
├── agent/         core logic — Claude API wrapper, data models, run logging
├── adapters/      LinkedIn RPS CSV import, Dripify text-file export
├── workflows/     the 5 workflows + the pipeline orchestrator
├── prompts/       prompt templates (system + user) per workflow
├── tests/         unit tests and sample fixtures
└── data/          all generated output — gitignored (PDPA)
```

Run the tests with:

```bash
python -m unittest discover tests
```

## Compliance notes (PDPA)

- Candidate data is personal data under Singapore's PDPA. All candidate CSVs, generated
  drafts, qualification summaries, longlists, and run logs are written under `data/`,
  which is gitignored — **do not commit candidate data**.
- Retention: archive candidate data after **12 months** unless the candidate is placed.
- LinkedIn outreach is capped at **50 InMails/day** and runs only through the dedicated
  **WangXQ researcher account** — never a consultant's personal LinkedIn account.
- The confidential project documents (`*.docx`, `*.pdf`) are gitignored and kept local.
