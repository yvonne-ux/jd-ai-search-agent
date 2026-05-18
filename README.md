# JD AI Search Agent

AI-powered executive search agent for **JonDavidson Pte Ltd** — automates the
intake-to-longlist workflow. See `CLAUDE.md` for project context and `PLAN.md` for the
build plan. Scoped by `JD_AI_Agent_Developer_Brief_May2026.docx`.

## Status

**Phase 1A — project scaffold.** The CLI currently supports one command: `check`.

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

   Then open `.env` and paste your key after `ANTHROPIC_API_KEY=`.
   **Never commit `.env`** — it is gitignored.

## Usage

Verify the setup and API connection:

```bash
python main.py check
```

A successful run prints a confirmation message from Claude.

## Project layout

```
jd-ai-search-agent/
├── main.py        CLI entry point
├── agent/         core logic — Claude API wrapper, data models, run logging
├── adapters/      LinkedIn RPS CSV import, Dripify text-file export
├── workflows/     the 4 workflows — intake, inmail, qualification, longlist
├── prompts/       prompt templates (system + user) per the brief
├── tests/         unit tests
└── data/          candidate CSVs and generated output — gitignored (PDPA)
```

## Adjusting prompts

Prompt templates live in `prompts/` as plain text, separate from code — they can be
edited without changing Python. (Prompt files are added in build Steps 3–6; see
`PLAN.md`.)

## Compliance notes

- Candidate data is personal data under Singapore's PDPA. Keep all candidate CSVs and
  generated output inside `data/` (gitignored). Do not commit candidate data.
- Retention: archive candidate data after 12 months unless the candidate is placed.
- LinkedIn outreach is capped at 50 InMails/day via the WangXQ researcher account only.
