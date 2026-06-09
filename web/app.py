"""JD AI Search Agent — local web interface.

A thin Flask app that drives the existing CLI workflows through the three v1
screens (Intake → Ranking → InMail). Routes stay small; all real work lives in
``workflows/`` and persistence in ``web/store.py``. Run from the project root:

    python web/app.py

Then open http://localhost:5000 in Safari or Chrome.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

# Ensure the parent project and this folder are importable whether the app is
# run directly (``python web/app.py``) or imported by a WSGI server such as
# gunicorn (``web.app:create_app``). The bare ``import jd_extract`` / ``import
# store`` below rely on this folder being on sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEB_DIR = Path(__file__).resolve().parent
for _p in (_PROJECT_ROOT, _WEB_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import secrets  # noqa: E402

from flask import (  # noqa: E402  — sys.path setup must come first
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from adapters.linkedin_csv import load_candidates  # noqa: E402
from agent.claude_client import ClaudeClient, ClaudeError  # noqa: E402
from agent.models import Candidate, SearchCriteria  # noqa: E402
from workflows.inmail import MAX_WORDS, RoleContext, check_draft, draft_inmail  # noqa: E402
from workflows.intake import (  # noqa: E402
    BRIEF_FIELDS,
    MandateBrief,
    generate_search_criteria,
)
from workflows.pipeline import (  # noqa: E402
    Mandate,
    create_mandate,
    list_mandates,
    load_mandate,
)
from workflows.rank import rank_candidates  # noqa: E402

import candidate_extract  # noqa: E402  — web/ is on sys.path
import jd_extract  # noqa: E402  — web/ is on sys.path[0] when run directly
import store  # noqa: E402  — web/ is on sys.path[0] when run directly

# Max JD upload size (5 MB is well above any real PDF/DOCX of a single role).
_JD_MAX_BYTES = 5 * 1024 * 1024

# Criteria fields that are lists (rendered one-per-line) vs. scalar text.
_CRITERIA_LIST_FIELDS = [
    ("job_titles", "Job titles"),
    ("seniority_levels", "Seniority levels"),
    ("target_companies", "Target companies"),
    ("industries", "Industries"),
    ("locations", "Locations"),
    ("exclusions", "Exclusions"),
]


def _lines(value: str) -> List[str]:
    """Split a textarea value into a clean list (one item per line)."""
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent / "static"),
    )
    app.secret_key = os.environ.get(
        "FLASK_SECRET_KEY", "jd-search-agent-local-dev-key"
    )

    # ---------- optional password gate ----------
    # When APP_PASSWORD is set (i.e. on a shared/hosted deployment) the whole
    # app sits behind HTTP Basic Auth. Left unset locally, so `python web/app.py`
    # stays open for development. Username defaults to "jd" if not specified.
    _auth_user = os.environ.get("APP_USERNAME", "jd")
    _auth_pass = os.environ.get("APP_PASSWORD")

    @app.before_request
    def _require_password():
        if not _auth_pass:
            return None  # no password configured → open (local dev)
        auth = request.authorization
        if (
            auth
            and auth.type == "basic"
            and auth.username == _auth_user
            and secrets.compare_digest(auth.password or "", _auth_pass)
        ):
            return None
        return Response(
            "Authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="JD AI Search Agent"'},
        )

    # ---------- shared helpers ----------

    def current_mandate() -> Optional[Mandate]:
        slug = session.get("mandate_slug")
        return load_mandate(slug) if slug else None

    @app.context_processor
    def inject_current_mandate():
        """Make the current mandate available to every template."""
        slug = session.get("mandate_slug")
        mandate = load_mandate(slug) if slug else None
        if slug and mandate is None:
            session.pop("mandate_slug", None)
        return {"current_mandate": mandate}

    # ---------- mandate selection ----------

    @app.route("/")
    def index():
        return redirect(url_for("mandates"))

    @app.route("/mandates", methods=["GET"])
    def mandates():
        return render_template("mandates.html", mandates=list_mandates())

    @app.route("/mandates/new", methods=["POST"])
    def mandates_new():
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Mandate name is required.", "error")
            return redirect(url_for("mandates"))
        mandate = create_mandate(name)
        session["mandate_slug"] = mandate.folder.name
        flash(f"Created mandate “{mandate.name}”.", "success")
        return redirect(url_for("intake"))

    @app.route("/mandates/select", methods=["POST"])
    def mandates_select():
        slug = (request.form.get("slug") or "").strip()
        mandate = load_mandate(slug)
        if mandate is None:
            flash("That mandate no longer exists.", "error")
            return redirect(url_for("mandates"))
        session["mandate_slug"] = slug
        return redirect(url_for("workspace"))

    @app.route("/mandates/switch", methods=["POST"])
    def mandates_switch():
        session.pop("mandate_slug", None)
        return redirect(url_for("mandates"))

    @app.route("/workspace")
    def workspace():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        return render_template(
            "workspace.html",
            has_criteria=store.has_criteria(mandate),
            has_ranking=bool(store.load_rankings(mandate)),
            selected_count=len(store.load_selection(mandate)),
        )

    # ---------- Step 1: Intake → criteria ----------

    def _draft_key(mandate: Mandate) -> str:
        """Per-mandate key for the in-session draft brief (pre-Claude)."""
        return f"intake_draft::{mandate.folder.name}"

    def _extracted_key(mandate: Mandate) -> str:
        return f"intake_extracted::{mandate.folder.name}"

    def _snapshot_key(mandate: Mandate) -> str:
        """Per-mandate key for a snapshot of the last JD extraction's values.
        Lets us tell on the next upload whether a previously-extracted field
        has been edited by the consultant — if it has, we preserve it."""
        return f"intake_snapshot::{mandate.folder.name}"

    def _load_session_draft(mandate: Mandate) -> Optional[MandateBrief]:
        data = session.get(_draft_key(mandate))
        if not data:
            return None
        return MandateBrief.from_dict(data)

    def _save_session_draft(
        mandate: Mandate, brief: MandateBrief, extracted: Optional[set] = None,
        snapshot: Optional[dict] = None,
    ) -> None:
        session[_draft_key(mandate)] = {
            field: getattr(brief, field, "") for field, _ in BRIEF_FIELDS
        }
        if extracted is not None:
            session[_extracted_key(mandate)] = sorted(extracted)
        if snapshot is not None:
            session[_snapshot_key(mandate)] = snapshot

    def _clear_session_draft(mandate: Mandate) -> None:
        session.pop(_draft_key(mandate), None)
        session.pop(_extracted_key(mandate), None)
        session.pop(_snapshot_key(mandate), None)

    @app.route("/intake")
    def intake():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        # Live session draft wins — it reflects the latest upload/edits. Fall
        # back to the brief persisted in criteria.json from a prior generate
        # run so the form isn't blank when the consultant returns to /intake.
        session_draft = _load_session_draft(mandate)
        if session_draft is not None:
            brief = session_draft
            extracted = set(session.get(_extracted_key(mandate), []))
        else:
            brief = store.load_brief(mandate) or MandateBrief()
            extracted = set()
        filled, total = jd_extract.field_completeness(brief)
        return render_template(
            "intake.html",
            step="intake",
            fields=BRIEF_FIELDS,
            brief=brief,
            extracted_fields=extracted,
            jd_filename=session.get(f"intake_filename::{mandate.folder.name}"),
            completeness_filled=filled,
            completeness_total=total,
            completeness_pct=int(round(filled * 100 / total)) if total else 0,
        )

    @app.route("/intake/upload", methods=["POST"])
    def intake_upload():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        upload = request.files.get("jd_file")
        if upload is None or not upload.filename:
            flash("Choose a JD file (PDF, Word, or text).", "error")
            return redirect(url_for("intake"))
        blob = upload.read(_JD_MAX_BYTES + 1)
        if len(blob) > _JD_MAX_BYTES:
            flash("That file is over 5 MB — please trim it before uploading.", "error")
            return redirect(url_for("intake"))
        try:
            text = jd_extract.read_jd_file(upload.filename, blob)
        except jd_extract.ExtractError as exc:
            flash(str(exc), "error")
            return redirect(url_for("intake"))

        # Uploading a JD means "fill the brief from THIS document". Run
        # extraction from scratch and replace the session draft entirely —
        # no merging with stale state. The consultant edits AFTER upload;
        # any in-form edits not yet submitted will be replaced.
        previously_extracted = set(session.get(_extracted_key(mandate), []))
        merged, just_extracted = jd_extract.extract_brief(text)

        if just_extracted:
            snapshot = {f: getattr(merged, f, "") for f in just_extracted}
            _save_session_draft(
                mandate, merged, just_extracted, snapshot=snapshot
            )
            # Persist the full JD text so /intake/generate can pass it to
            # Claude alongside the brief.
            store.save_jd_source(mandate, text)
            session[f"intake_filename::{mandate.folder.name}"] = upload.filename
            verb = "Re-read" if previously_extracted else "Read"
            flash(
                f"{verb} {upload.filename} — {len(just_extracted)} field"
                f"{'s' if len(just_extracted) != 1 else ''} pre-filled from "
                "the JD. Review and edit before generating criteria.",
                "success",
            )
        else:
            flash(
                f"Read {upload.filename}, but couldn't confidently fill any "
                "fields. Please complete the brief manually.",
                "error",
            )
        return redirect(url_for("intake"))

    @app.route("/intake/clear", methods=["POST"])
    def intake_clear():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        _clear_session_draft(mandate)
        store.clear_jd_source(mandate)
        session.pop(f"intake_filename::{mandate.folder.name}", None)
        flash("Intake brief cleared.", "success")
        return redirect(url_for("intake"))

    @app.route("/intake/generate", methods=["POST"])
    def intake_generate():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        brief = MandateBrief.from_dict(
            {field: request.form.get(field, "") for field, _ in BRIEF_FIELDS}
        )
        # Persist as a session draft *before* the Claude call so a transient
        # API failure doesn't lose the consultant's edits.
        _save_session_draft(mandate, brief)
        # The full JD text (if a file was uploaded) is sent to Claude alongside
        # the brief so target_companies / industries / job_titles are grounded
        # in the actual role rather than generic defaults.
        jd_text = store.load_jd_source(mandate)
        try:
            client = ClaudeClient()
            criteria = generate_search_criteria(brief, client, jd_text=jd_text)
        except ClaudeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("intake"))
        store.save_intake(mandate, brief, criteria)
        _clear_session_draft(mandate)
        session.pop(f"intake_filename::{mandate.folder.name}", None)
        flash("Search criteria generated. Review and edit before ranking.", "success")
        return redirect(url_for("criteria"))

    @app.route("/criteria")
    def criteria():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        crit = store.load_criteria(mandate)
        if crit is None:
            flash("Generate search criteria first.", "error")
            return redirect(url_for("intake"))
        return render_template(
            "criteria.html",
            step="intake",
            criteria=crit,
            list_fields=_CRITERIA_LIST_FIELDS,
        )

    @app.route("/criteria/save", methods=["POST"])
    def criteria_save():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        crit = SearchCriteria(
            job_titles=_lines(request.form.get("job_titles")),
            seniority_levels=_lines(request.form.get("seniority_levels")),
            target_companies=_lines(request.form.get("target_companies")),
            industries=_lines(request.form.get("industries")),
            locations=_lines(request.form.get("locations")),
            boolean_string=(request.form.get("boolean_string") or "").strip(),
            exclusions=_lines(request.form.get("exclusions")),
            search_rationale=(request.form.get("search_rationale") or "").strip(),
        )
        store.save_criteria_edits(mandate, crit)
        flash("Criteria saved.", "success")
        return redirect(url_for("criteria"))

    # ---------- Step 2: Candidate ranking ----------

    @app.route("/rank")
    def rank():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        crit = store.load_criteria(mandate)
        if crit is None:
            flash("Generate search criteria before ranking candidates.", "error")
            return redirect(url_for("intake"))
        rankings = store.load_rankings(mandate)
        selected = set(store.load_selection(mandate))
        return render_template(
            "rank.html",
            step="rank",
            criteria=crit,
            rankings=rankings,
            selected=selected,
            has_csv=store.has_candidates_csv(mandate),
        )

    @app.route("/rank/run", methods=["POST"])
    def rank_run():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        crit = store.load_criteria(mandate)
        if crit is None:
            flash("Generate search criteria before ranking candidates.", "error")
            return redirect(url_for("intake"))

        upload = request.files.get("csv")
        if upload is None or not upload.filename:
            flash("Choose a LinkedIn RPS CSV export to upload.", "error")
            return redirect(url_for("rank"))

        store.save_candidates_csv(mandate, upload.read())
        candidates = load_candidates(store.candidates_csv_path(mandate))
        if not candidates:
            flash("No candidates found in that CSV — check the export format.", "error")
            return redirect(url_for("rank"))

        try:
            client = ClaudeClient()
            rankings = rank_candidates(candidates, crit, client)
        except ClaudeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("rank"))
        store.save_rankings(mandate, rankings)
        flash(f"Ranked {len(rankings)} candidates.", "success")
        return redirect(url_for("rank"))

    @app.route("/rank/paste", methods=["POST"])
    def rank_paste():
        """Extract candidates from text pasted off a LinkedIn Recruiter page
        (no Chrome extension / no CSV needed) and rank them."""
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        crit = store.load_criteria(mandate)
        if crit is None:
            flash("Generate search criteria before ranking candidates.", "error")
            return redirect(url_for("intake"))

        pasted = (request.form.get("pasted") or "").strip()
        if not pasted:
            flash("Paste the candidates from your LinkedIn Recruiter results first.", "error")
            return redirect(url_for("rank"))

        try:
            client = ClaudeClient()
            candidates = candidate_extract.extract_candidates(pasted, client)
            if not candidates:
                flash(
                    "Couldn't find any candidates in the pasted text. Make sure "
                    "you copied the results list (names, titles, locations).",
                    "error",
                )
                return redirect(url_for("rank"))
            rankings = rank_candidates(candidates, crit, client)
        except ClaudeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("rank"))
        store.save_rankings(mandate, rankings)
        flash(
            f"Extracted and ranked {len(rankings)} candidates from pasted text.",
            "success",
        )
        return redirect(url_for("rank"))

    @app.route("/rank/select", methods=["POST"])
    def rank_select():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        selected = [n for n in request.form.getlist("selected") if n.strip()]
        if not selected:
            flash("Select at least one candidate to draft outreach for.", "error")
            return redirect(url_for("rank"))
        store.save_selection(mandate, selected)
        return redirect(url_for("inmail"))

    # ---------- Step 3: InMail drafts ----------

    def _selected_candidates(mandate: Mandate) -> List[Candidate]:
        """Candidates whose names are in the saved selection, ranking order."""
        names = [n.strip().lower() for n in store.load_selection(mandate)]
        if not names or not store.has_candidates_csv(mandate):
            return []
        by_name = {
            c.name.strip().lower(): c
            for c in load_candidates(store.candidates_csv_path(mandate))
        }
        ordered = [by_name[n] for n in names if n in by_name]
        return ordered

    @app.route("/inmail")
    def inmail():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        candidates = _selected_candidates(mandate)
        drafts = []
        for cand in candidates:
            text = store.load_draft(mandate, cand.name)
            drafts.append(
                {
                    "candidate": cand,
                    "text": text,
                    "warnings": check_draft(text) if text else [],
                }
            )
        return render_template(
            "inmail.html",
            step="inmail",
            drafts=drafts,
            selling_point=store.load_selling_point(mandate),
            max_words=MAX_WORDS,
        )

    @app.route("/inmail/generate", methods=["POST"])
    def inmail_generate():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        candidates = _selected_candidates(mandate)
        if not candidates:
            flash("No selected candidates — pick some on the Ranking screen.", "error")
            return redirect(url_for("rank"))

        selling_point = (request.form.get("selling_point") or "").strip()
        store.save_selling_point(mandate, selling_point)
        role = RoleContext.from_intake_file(
            store.criteria_path(mandate), selling_point=selling_point
        )
        try:
            client = ClaudeClient()
            for cand in candidates:
                draft = draft_inmail(cand, role, client)
                store.save_draft(mandate, cand.name, draft)
        except ClaudeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("inmail"))
        flash(f"Drafted {len(candidates)} InMails.", "success")
        return redirect(url_for("inmail"))

    @app.route("/inmail/save", methods=["POST"])
    def inmail_save():
        mandate = current_mandate()
        if mandate is None:
            return redirect(url_for("mandates"))
        name = (request.form.get("candidate_name") or "").strip()
        text = request.form.get("draft") or ""
        if not name:
            flash("Missing candidate name.", "error")
            return redirect(url_for("inmail"))
        store.save_draft(mandate, name, text)
        flash(f"Saved draft for {name}.", "success")
        return redirect(url_for("inmail"))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
