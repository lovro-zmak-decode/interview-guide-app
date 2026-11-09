"""
Flask app: upload a candidate's CV + LinkedIn info, optionally pick curated
questions from the Own/Shared Questions DB, generate a first-interview
summary with an LLM, download the result as a .docx.

Accounts are invite-only (see interview_app/auth.py): the first run redirects
to a one-time /setup page to create the first account (full/superadmin
access); afterwards, the superadmin creates further accounts from
/admin/users.

Run locally:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your API key(s)
    python app.py
Then open http://127.0.0.1:5001
"""

from __future__ import annotations

import glob
import io
import json
import os
import re
import uuid
import logging
from collections import OrderedDict
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, flash, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from sqlalchemy import inspect, text

from interview_app.auth import auth_bp, admin_required
from interview_app.extractors import extract_text_from_file, gather_research
from interview_app.llm_providers import get_provider, available_providers, LLMConfigError
from interview_app.models import GeneratedGuide, InterviewLog, InterviewRole, Question, QuestionGroup, SystemPrompt, User, db
from interview_app.question_bank import qb_bp
from interview_app.roles import roles_bp
from interview_app.shared_questions import shared_qb_bp
from interview_app.system_prompts import system_prompts_bp
from interview_app.summarizer import generate_interview_debrief, generate_interview_summary, SummaryGenerationError
from interview_app import interview_log as ilog
from interview_app.docx_generator import build_docx
from interview_app.schema import (
    CuratedQuestionGroup,
    InterviewQuestion,
    InterviewSummary,
    WRAP_UP_MINUTES,
    estimate_section_minutes,
    estimate_total_minutes,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)

ALLOWED_CV_EXTENSIONS = {".pdf", ".docx", ".txt"}

# While an interview is running, edits are sent to the server at most this often.
INTERVIEW_AUTOSAVE_SECONDS = 30
# How often an open report asks the server for what the other interviewers wrote.
INTERVIEW_POLL_SECONDS = 5

# Create app using factory function
from interview_app import create_app
app = create_app()
UPLOAD_DIR = app.config["UPLOAD_DIR"]
GENERATED_DIR = app.config["GENERATED_DIR"]


app.register_blueprint(auth_bp)
app.register_blueprint(qb_bp)
app.register_blueprint(shared_qb_bp)
app.register_blueprint(roles_bp)
app.register_blueprint(system_prompts_bp)


@app.before_request
def require_setup_or_login():
    # Allow the bootstrap page and static assets even with zero users / not logged in.
    if request.endpoint in ("auth.setup", "static"):
        return None
    if User.query.count() == 0:
        return redirect(url_for("auth.setup"))
    return None


def _get_accessible_guide(guide_id_raw) -> GeneratedGuide | None:
    """The guide with this id if the current user may see it (owner or admin),
    else None. Used for cloning, where a bad/foreign id just means "no source"."""
    if not guide_id_raw or not str(guide_id_raw).isdigit():
        return None
    guide = db.session.get(GeneratedGuide, int(guide_id_raw))
    if guide is None or (guide.user_id != current_user.id and not current_user.is_admin):
        return None
    return guide


def _render_index(prefill: dict | None = None):
    groups = QuestionGroup.visible_to(current_user).all()
    # Most recently updated first — the top one is also what generation falls
    # back to if no prompt is explicitly picked, so it doubles as the sane
    # default selection in the dropdown.
    system_prompts = (
        SystemPrompt.query.filter_by(type="technical").order_by(SystemPrompt.updated_at.desc()).all()
    )
    return render_template(
        "index.html",
        providers=available_providers(),
        default_provider=os.getenv("LLM_PROVIDER", "openai"),
        question_groups=groups,
        interview_roles=InterviewRole.all_sorted(),
        system_prompts=system_prompts,
        prefill=prefill,
    )


@app.route("/", methods=["GET"])
@login_required
def index():
    return _render_index()


@app.route("/history/<int:guide_id>/clone", methods=["GET"])
@login_required
def clone_guide(guide_id: int):
    """The generate form prefilled from an earlier guide, so it can be
    regenerated with different settings without re-entering everything."""
    guide = _get_accessible_guide(guide_id)
    if guide is None:
        flash("You don't have access to this guide.")
        return redirect(url_for("history"))

    summary = InterviewSummary.model_validate_json(guide.summary_json)
    try:
        question_ids = [int(i) for i in json.loads(guide.question_ids_json or "[]")]
    except (ValueError, TypeError):
        question_ids = []

    prefill = {
        "guide_id": guide.id,
        "candidate_name": guide.candidate_name,
        "role_title": guide.role_title,
        "duration_minutes": summary.duration_minutes,
        "provider": guide.provider_used,
        "prompt_id": guide.prompt_id,
        "question_ids": set(question_ids),
        "has_research": bool(guide.research_text),
        "additional_notes": guide.additional_notes or "",
    }
    return _render_index(prefill)


def _display_name(user: User) -> str:
    return user.email.split("@")[0]


def _participant_logs(guide: GeneratedGuide, full: bool = False) -> list[dict]:
    """Everyone's notes on this guide that have any content or an interview in
    progress, oldest first, each as {"user_id", "name", "started", "data"}.
    Unless `full` is set, only the current user's own entry is complete; for
    everyone else the scoring is removed (see interview_log.shareable)."""
    logs = InterviewLog.query.filter_by(guide_id=guide.id).order_by(InterviewLog.id).all()
    out = []
    for log in logs:
        data = ilog.parse_data(log.data_json)
        if log.user_id != current_user.id and not full:
            data = ilog.shareable(data)
        if log.started or ilog.has_content(data):
            out.append({"user_id": log.user_id, "name": _display_name(log.user), "started": log.started, "data": data})
    return out


def _interview_context(guide: GeneratedGuide, summary: InterviewSummary) -> dict:
    """Template variables for result.html. Whoever can open a guide (its owner
    or an admin) takes part in the interview with their own notes; everyone
    else's notes are shown read-only next to them."""
    log = InterviewLog.for_guide_and_user(guide.id, current_user.id)
    started = bool(log and log.started)
    return {
        "guide_id": guide.id,
        "can_edit": True,
        "iv": ilog.parse_data(log.data_json if log else None),
        "iv_started": started,
        "iv_editing": started,
        "rec_options": ilog.recommendation_options(summary),
        "autosave_seconds": INTERVIEW_AUTOSAVE_SECONDS,
        "poll_seconds": INTERVIEW_POLL_SECONDS,
        "others": [p for p in _participant_logs(guide) if p["user_id"] != current_user.id],
    }


def _participant_guide_or_error(guide_id: int):
    """(guide, None) if the current user may take part in this guide's interview
    (its owner or an admin), else (None, json error response)."""
    guide = db.session.get(GeneratedGuide, guide_id)
    if guide is None:
        return None, (jsonify(error="Guide not found."), 404)
    if guide.user_id != current_user.id and not current_user.is_admin:
        return None, (jsonify(error="You don't have access to this guide."), 403)
    return guide, None


@app.route("/history/<int:guide_id>/others", methods=["GET"])
@login_required
def interview_others(guide_id: int):
    """What the other interviewers have written so far, polled by the open report."""
    guide, error = _participant_guide_or_error(guide_id)
    if error:
        return error
    return jsonify(others=[p for p in _participant_logs(guide) if p["user_id"] != current_user.id])


def _get_or_create_log(guide: GeneratedGuide) -> InterviewLog:
    log = InterviewLog.for_guide_and_user(guide.id, current_user.id)
    if log is None:
        log = InterviewLog(guide_id=guide.id, user_id=current_user.id, data_json="{}")
        db.session.add(log)
    return log


@app.route("/history/<int:guide_id>/log", methods=["POST"])
@login_required
def save_interview_log(guide_id: int):
    guide, error = _participant_guide_or_error(guide_id)
    if error:
        return error
    if request.content_length and request.content_length > ilog.MAX_BODY_BYTES:
        return jsonify(error="Too much text in one save."), 413
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Expected a JSON object."), 400

    summary = InterviewSummary.model_validate_json(guide.summary_json)
    log = _get_or_create_log(guide)
    try:
        data = ilog.merge_update(ilog.parse_data(log.data_json), payload, summary)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if "started" in payload:
        log.started = bool(payload["started"])
    log.data_json = json.dumps(data, ensure_ascii=False)
    db.session.commit()
    return jsonify(ok=True)


@app.route("/history/<int:guide_id>/summary", methods=["POST"])
@login_required
def generate_guide_debrief(guide_id: int):
    """Writes (or rewrites) the AI summary from the current user's own notes,
    for them to review. Replaces their earlier summary and marks it unreviewed."""
    guide, error = _participant_guide_or_error(guide_id)
    if error:
        return error

    summary = InterviewSummary.model_validate_json(guide.summary_json)
    log = _get_or_create_log(guide)
    data = ilog.parse_data(log.data_json)
    variables = {
        "candidate_name": summary.candidate_name,
        "role_title": summary.role_title,
        "candidate_profile": summary.profile_and_goals,
        "questions_and_answers": ilog.questions_and_answers_text(summary, data["answers"]),
        "live_notes": data["live_notes"].strip() or "(no notes)",
        "evaluation": ilog.evaluation_text(summary, data["evaluation"]),
        "overall_recommendation": data["recommendation"] or "(not set)",
    }
    try:
        provider = get_provider(guide.provider_used)
        debrief = generate_interview_debrief(provider, variables)
    except (LLMConfigError, SummaryGenerationError) as exc:
        return jsonify(error=str(exc)), 502
    except Exception as exc:
        logging.exception("Summary generation failed")
        return jsonify(error=f"The model call failed: {exc}"), 502

    ilog.store_summary(data, debrief.summary, debrief.second_round_suggestions)
    log.data_json = json.dumps(data, ensure_ascii=False)
    db.session.commit()
    return jsonify(ok=True)


def _section_minutes(summary: InterviewSummary) -> dict:
    """Recommended-time estimates shown next to each section heading on the
    result page — same numbers docx_generator puts in the downloaded file,
    computed from the actual question counts (~3 min/question), not asked of
    the LLM. See schema.estimate_section_minutes/estimate_total_minutes."""
    technical_count = len(summary.quick_check_questions) + len(summary.deep_dive_questions)
    return {
        "warmup": estimate_section_minutes(len(summary.warmup_questions)),
        "technical": estimate_section_minutes(technical_count),
        "thinking": estimate_section_minutes(len(summary.thinking_questions)),
        "teamwork": estimate_section_minutes(len(summary.teamwork_questions)),
        "wrapup": WRAP_UP_MINUTES,
        "total": estimate_total_minutes(summary),
    }


def _collect_curated_groups(question_ids: list[int]) -> list[tuple[str, list[Question]]]:
    """Given selected question IDs, return (group_name, [Question]) only for
    questions the current user is allowed to see (the shared DB, or their own
    private groups), preserving group order and question order.

    These are the questions the interviewer picked ahead of time. The LLM
    only sees them as an optional pool to draw from (see
    prompts.format_curated_groups) — it decides which ones (if any) fit this
    candidate and the interview's time budget. The full, unmodified list
    built here is what ends up as the "Additional questions from the
    Questions DB" reference section at the end of the generated guide,
    regardless of which of them the model actually used."""
    if not question_ids:
        return []

    visible_group_ids = {g.id for g in QuestionGroup.visible_to(current_user).all()}
    questions = (
        Question.query.filter(Question.id.in_(question_ids))
        .order_by(Question.group_id, Question.position)
        .all()
    )

    grouped: "OrderedDict[str, list[Question]]" = OrderedDict()
    for q in questions:
        if q.group_id not in visible_group_ids:
            continue
        grouped.setdefault(q.group.name, []).append(q)

    return list(grouped.items())


def _build_reference_question_groups(curated_groups: list[tuple[str, list[Question]]]) -> list[CuratedQuestionGroup]:
    """The authoritative "Additional questions from the Questions DB" appendix —
    built directly from the interviewer's original selection, not from
    anything the LLM returned, so it's always complete and accurate no matter
    which of these questions the model chose to weave into the timed guide.
    Each question's own explanation (if any) stands in for guidance, same as
    the group-preview docx feature."""
    return [
        CuratedQuestionGroup(
            group_name=name,
            questions=[
                InterviewQuestion(
                    question=q.question_text,
                    guidance=(q.explanation or "").strip() or "(no explanation provided for this question)",
                )
                for q in qs
            ],
        )
        for name, qs in curated_groups
    ]


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    candidate_name = request.form.get("candidate_name", "").strip()
    role_title = request.form.get("role_title", "").strip()
    duration_minutes = int(request.form.get("duration_minutes") or 60)
    provider_name = request.form.get("provider") or None
    additional_notes = request.form.get("additional_notes", "").strip()
    linkedin_text_input = request.form.get("linkedin_text", "").strip()
    prompt_id_raw = request.form.get("prompt_id")
    prompt_id = int(prompt_id_raw) if prompt_id_raw and prompt_id_raw.isdigit() else None

    cv_file = request.files.get("cv_file")
    linkedin_file = request.files.get("linkedin_file")

    selected_question_ids = [int(v) for v in request.form.getlist("question_ids") if v.isdigit()]

    # Cloning: reuse the research text stored on an earlier guide (the
    # candidate's CV, LinkedIn and linked pages as already extracted) unless a
    # new CV is attached, in which case the form's own materials win.
    source_guide = _get_accessible_guide(request.form.get("clone_from"))
    stored_research = source_guide.research_text if source_guide else None
    has_new_cv = bool(cv_file and cv_file.filename)
    reuse_stored_research = not has_new_cv and bool(stored_research)

    if not has_new_cv and not reuse_stored_research:
        flash("Please attach the candidate's CV.")
        return redirect(url_for("index"))

    if role_title:
        # Register new interview role names typed on the form so they show up
        # as a suggestion next time — this is how "anyone can add a new one"
        # happens in practice.
        InterviewRole.get_or_create(role_title)

    run_id = uuid.uuid4().hex[:8]

    if reuse_stored_research:
        research_text = stored_research
        followed_links = []
    else:
        cv_ext = os.path.splitext(cv_file.filename)[1].lower()
        if cv_ext not in ALLOWED_CV_EXTENSIONS:
            flash(f"Unsupported CV format: {cv_ext}. Supported: {', '.join(ALLOWED_CV_EXTENSIONS)}")
            return redirect(url_for("index"))

        cv_path = os.path.join(UPLOAD_DIR, f"{run_id}_cv{cv_ext}")
        cv_file.save(cv_path)

        try:
            cv_text = extract_text_from_file(cv_path)
        except Exception as exc:
            flash(f"Failed to read the CV: {exc}")
            return redirect(url_for("index"))

        linkedin_text = linkedin_text_input
        if linkedin_file and linkedin_file.filename:
            li_ext = os.path.splitext(linkedin_file.filename)[1].lower()
            if li_ext in ALLOWED_CV_EXTENSIONS:
                li_path = os.path.join(UPLOAD_DIR, f"{run_id}_linkedin{li_ext}")
                linkedin_file.save(li_path)
                try:
                    linkedin_text = extract_text_from_file(li_path) or linkedin_text
                except Exception as exc:
                    flash(f"Failed to read the LinkedIn file: {exc}")

        if not cv_text.strip() and not linkedin_text.strip():
            flash("Couldn't extract any text from the attached materials.")
            return redirect(url_for("index"))

        research = gather_research(cv_text, linkedin_text)
        research_text = research.as_prompt_text()
        followed_links = research.linked_pages

    curated_groups = _collect_curated_groups(selected_question_ids)
    # Only the question_text flows into the pool offered to the LLM — the
    # explanation is interviewer-facing detail, not part of the prompt.
    curated_groups_for_prompt = [(name, [q.question_text for q in qs]) for name, qs in curated_groups]

    try:
        provider = get_provider(provider_name)
    except LLMConfigError as exc:
        flash(str(exc))
        return redirect(url_for("index"))

    try:
        summary = generate_interview_summary(
            provider=provider,
            research_text=research_text,
            candidate_name=candidate_name or None,
            role_title=role_title or None,
            duration_minutes=duration_minutes,
            curated_groups=curated_groups_for_prompt,
            prompt_id=prompt_id,
            additional_notes=additional_notes,
        )
    except SummaryGenerationError as exc:
        flash(f"Failed to generate the summary: {exc}")
        return redirect(url_for("index"))

    # The reference appendix always reflects the interviewer's original
    # selection, never whatever (if anything) the model echoed back — see
    # _build_reference_question_groups.
    summary.curated_question_groups = _build_reference_question_groups(curated_groups)

    generated_at = datetime.now()
    docx_filename = f"interview_guide_{run_id}.docx"
    docx_path = os.path.join(GENERATED_DIR, docx_filename)
    build_docx(summary, docx_path, generated_at=generated_at)

    guide = GeneratedGuide(
        user_id=current_user.id,
        candidate_name=summary.candidate_name,
        role_title=summary.role_title,
        provider_used=provider.name,
        docx_filename=docx_filename,
        summary_json=summary.model_dump_json(),
        created_at=generated_at,
        research_text=research_text,
        question_ids_json=json.dumps([q.id for _, qs in curated_groups for q in qs]),
        prompt_id=prompt_id,
        additional_notes=additional_notes,
    )
    db.session.add(guide)
    db.session.commit()

    return render_template(
        "result.html",
        summary=summary,
        docx_filename=docx_filename,
        followed_links=followed_links,
        provider_used=provider.name,
        generated_at=generated_at,
        section_minutes=_section_minutes(summary),
        **_interview_context(guide, summary),
    )


@app.route("/history", methods=["GET"])
@login_required
def history():
    guides = GeneratedGuide.list_for(current_user).all()
    return render_template("history.html", guides=guides)


@app.route("/guides/all", methods=["GET"])
@admin_required
def all_guides():
    """Admin-only: every guide generated by every user, most recent first,
    with a column showing who generated each one — unlike "My guides", which
    is scoped to the current user."""
    guides = GeneratedGuide.list_all().all()
    return render_template("all_guides.html", guides=guides)


@app.route("/history/<int:guide_id>", methods=["GET"])
@login_required
def history_view(guide_id: int):
    guide = GeneratedGuide.query.get_or_404(guide_id)
    if guide.user_id != current_user.id and not current_user.is_admin:
        flash("You don't have access to this guide.")
        return redirect(url_for("history"))

    summary = InterviewSummary.model_validate_json(guide.summary_json)
    return render_template(
        "result.html",
        summary=summary,
        docx_filename=guide.docx_filename,
        followed_links=[],
        provider_used=guide.provider_used,
        generated_at=guide.created_at,
        section_minutes=_section_minutes(summary),
        guide_owner=guide.user,
        **_interview_context(guide, summary),
    )


@app.route("/history/<int:guide_id>/delete", methods=["POST"])
@login_required
def delete_guide(guide_id: int):
    guide = _get_accessible_guide(guide_id)
    if guide is None:
        flash("You don't have access to this guide.")
        return redirect(url_for("history"))

    name = guide.candidate_name
    # Files are named after the run id (interview_guide_<runid>.docx,
    # <runid>_cv.*, <runid>_linkedin.*), so remove the generated document and
    # the uploaded source files together with the guide.
    match = re.fullmatch(r"interview_guide_([0-9a-f]{8})\.docx", guide.docx_filename or "")
    if match:
        run_id = match.group(1)
        for directory, pattern in ((GENERATED_DIR, f"interview_guide_{run_id}.docx"),
                                   (UPLOAD_DIR, f"{run_id}_*")):
            for path in glob.glob(os.path.join(directory, pattern)):
                try:
                    os.remove(path)
                except OSError:
                    logging.warning("Could not remove %s", path)

    db.session.delete(guide)
    db.session.commit()
    flash(f"Deleted the guide for {name}.")
    if request.form.get("next") == "all_guides" and current_user.is_admin:
        return redirect(url_for("all_guides"))
    return redirect(url_for("history"))


@app.route("/download/<path:filename>", methods=["GET"])
@login_required
def download(filename: str):
    safe_name = os.path.basename(filename)
    safe_path = os.path.join(GENERATED_DIR, safe_name)
    if not os.path.isfile(safe_path):
        flash("The file doesn't exist or has expired.")
        return redirect(url_for("index"))

    # If this file is tracked as someone's generated guide, only its owner (or
    # an admin, for the "All guides" page) may download it. Untracked files
    # (shouldn't normally happen) are allowed through, since there's nothing
    # to check ownership against.
    guide = GeneratedGuide.query.filter_by(docx_filename=safe_name).first()
    if guide is not None and guide.user_id != current_user.id and not current_user.is_admin:
        flash("You don't have access to this file.")
        return redirect(url_for("index"))

    if guide is not None:
        logs = [
            {"name": p["name"], **p["data"]}
            for p in _participant_logs(guide, full=True)
            if ilog.has_content(p["data"])
        ]
        if logs:
            # The Word report is the complete record: everyone's notes and everyone's
            # scoring, labelled by name. On the page the scoring stays private.
            buffer = io.BytesIO()
            build_docx(
                InterviewSummary.model_validate_json(guide.summary_json),
                buffer,
                generated_at=guide.created_at,
                logs=logs,
            )
            buffer.seek(0)
            return send_file(buffer, as_attachment=True, download_name=safe_name)

    return send_file(safe_path, as_attachment=True)


def _migrate_role_tag_table() -> None:
    """The InterviewRole model used to be called RoleTag / table `role_tag`.
    If an old database still has that table (and hasn't been migrated yet),
    just rename it in place — the schema itself didn't change."""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if "role_tag" in tables and "interview_role" not in tables:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE role_tag RENAME TO interview_role"))


def _migrate_user_table() -> None:
    """Older databases had `user.username` + `user.is_admin` instead of
    `user.email` + `user.role`. SQLite can't add a NOT NULL/UNIQUE column or
    drop columns cleanly with a plain ALTER TABLE, so rebuild the table:
    copy the data across (mapping is_admin -> role, and username -> email,
    special-casing the original bootstrap account so it becomes the DECODE
    work email), then swap the old table out."""
    inspector = inspect(db.engine)
    if "user" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("user")}
    if "username" not in columns and "is_admin" not in columns:
        return  # already on the new schema

    with db.engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE user_migrated (
                id INTEGER PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                created_at DATETIME
            )
            """
        ))
        rows = conn.execute(text(
            "SELECT id, username, password_hash, is_admin, created_at FROM user"
        )).fetchall()
        for row in rows:
            email = "lovro.zmak@decode.agency" if row.username == "lovrozmak" else row.username
            role = "superadmin" if row.is_admin else "user"
            conn.execute(
                text(
                    "INSERT INTO user_migrated (id, email, password_hash, role, created_at) "
                    "VALUES (:id, :email, :password_hash, :role, :created_at)"
                ),
                {
                    "id": row.id,
                    "email": email,
                    "password_hash": row.password_hash,
                    "role": role,
                    "created_at": row.created_at,
                },
            )
        conn.execute(text("DROP TABLE user"))
        conn.execute(text("ALTER TABLE user_migrated RENAME TO user"))


def _migrate_system_prompt_scoring_rows_column() -> None:
    """Adds SystemPrompt.scoring_rows (the configurable "Quick evaluation"
    rows prop) to any existing system_prompt table that predates it. A plain
    ALTER TABLE ADD COLUMN is enough here — no NOT NULL/UNIQUE tightening
    involved like the user-table migration above."""
    inspector = inspect(db.engine)
    if "system_prompt" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("system_prompt")}
    if "scoring_rows" in columns:
        return
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE system_prompt ADD COLUMN scoring_rows TEXT NOT NULL DEFAULT ''"))


def _migrate_question_table() -> None:
    """Older databases had `question.text` instead of `question.question_text`
    and no `explanation` column. Plain ALTER TABLE RENAME COLUMN / ADD COLUMN
    is enough here — no NOT NULL/UNIQUE tightening involved."""
    inspector = inspect(db.engine)
    if "question" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("question")}
    with db.engine.begin() as conn:
        if "text" in columns and "question_text" not in columns:
            conn.execute(text("ALTER TABLE question RENAME COLUMN text TO question_text"))
        if "explanation" not in columns:
            conn.execute(text("ALTER TABLE question ADD COLUMN explanation TEXT NOT NULL DEFAULT ''"))


def _migrate_generated_guide_clone_columns() -> None:
    """Adds the columns that let a guide be cloned (its stored research text,
    selected question ids and prompt id) to a generated_guide table that
    predates them. Idempotent, and also run at import time because production
    (gunicorn) never goes through init_db()."""
    inspector = inspect(db.engine)
    if "generated_guide" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("generated_guide")}
    wanted = {"research_text": "TEXT", "question_ids_json": "TEXT", "prompt_id": "INTEGER", "additional_notes": "TEXT"}
    with db.engine.begin() as conn:
        for name, sql_type in wanted.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE generated_guide ADD COLUMN {name} {sql_type}"))


with app.app_context():
    _migrate_role_tag_table()
    db.create_all()
    _migrate_generated_guide_clone_columns()


def init_db():
    with app.app_context():
        _migrate_role_tag_table()
        db.create_all()
        _migrate_user_table()
        _migrate_system_prompt_scoring_rows_column()
        _migrate_question_table()
        _migrate_generated_guide_clone_columns()


if __name__ == "__main__":
    init_db()
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", "5001"))
    app.run(host=host, port=port, debug=debug)
