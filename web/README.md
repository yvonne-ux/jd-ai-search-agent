# Web interface — JD AI Search Agent

A local browser UI for the JD AI Search Agent. See `CLAUDE.md` in this folder
for the design, and `PLAN.md` for the build plan.

## Run it

From the project root:

```bash
source venv/bin/activate
pip install -r requirements.txt        # picks up Flask if not already installed
python web/app.py
```

Then open <http://localhost:5000> in Safari or Chrome.

## What works today (Step 1)

- Landing page lists existing mandates and lets you create a new one.
- Selecting or creating a mandate stores it in your browser session and
  carries it as a chip in the JD-branded header on every page.
- “Switch mandate” in the header returns you to the mandate list.

The three working screens — **Intake**, **Candidate Ranking**, **InMail
Drafts** — land in Steps 2–4 of `PLAN.md`.

## Where things live

```
web/
├── app.py            Flask app + routes
├── templates/        Jinja templates
├── static/           CSS + small amount of vanilla JS
├── CLAUDE.md         Web interface design / scope
├── PLAN.md           Build plan
└── README.md         This file
```

Mandate workspaces live one level up in `data/mandates/<slug>/` — the same
folder the CLI uses, so a consultant can switch between CLI and web on the
same mandate.

## Stopping the server

`Ctrl-C` in the terminal where it is running.
