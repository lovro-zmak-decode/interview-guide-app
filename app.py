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

import os
import uuid
import logging
from collections import OrderedDict
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from sqlalchemy import inspect, text

from interview_app.auth import auth_bp, admin_required
from interview_app.extractors import extract_text_from_file, gather_research
from interview_app.llm_providers import get_provider, available_providers, LLMConfigError
from interview_app.models import GeneratedGuide, InterviewRole, Question, QuestionGroup, SystemPrompt, User, db
from interview_app.question_bank import qb_bp
from interview_app.roles import roles_bp
from interview_app.shared_questions import shared_qb_bp
from interview_app.system_prompts import system_prompts_bp
from interview_app.summarizer import generate_interview_summary, SummaryGenerationError
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

# Create app using factory function
from interview_app import create_app
app = create_app()


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


@app.route("/", methods=["GET"])
@login_required
def index():
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
        default_provider=os.getenv("LLM_PROVIDER", "claude"),
        question_groups=groups,
        interview_roles=InterviewRole.all_sorted(),
        system_prompts=system_prompts,
    )


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
    linkedin_text_input = request.form.get("linkedin_text", "").strip()
    prompt_id_raw = request.form.get("prompt_id")
    prompt_id = int(prompt_id_raw) if prompt_id_raw and prompt_id_raw.isdigit() else None

    cv_file = request.files.get("cv_file")
    linkedin_file = request.files.get("linkedin_file")

    selected_question_ids = [int(v) for v in request.form.getlist("question_ids") if v.isdigit()]

    if not cv_file or cv_file.filename == "":
        flash("Please attach the candidate's CV.")
        return redirect(url_for("index"))

    if role_title:
        # Register new interview role names typed on the form so they show up
        # as a suggestion next time — this is how "anyone can add a new one"
        # happens in practice.
        InterviewRole.get_or_create(role_title)

    cv_ext = os.path.splitext(cv_file.filename)[1].lower()
    if cv_ext not in ALLOWED_CV_EXTENSIONS:
        flash(f"Unsupported CV format: {cv_ext}. Supported: {', '.join(ALLOWED_CV_EXTENSIONS)}")
        return redirect(url_for("index"))

    run_id = uuid.uuid4().hex[:8]
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
            research_text=research.as_prompt_text(),
            candidate_name=candidate_name or None,
            role_title=role_title or None,
            duration_minutes=duration_minutes,
            curated_groups=curated_groups_for_prompt,
            prompt_id=prompt_id,
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
    )
    db.session.add(guide)
    db.session.commit()

    return render_template(
        "result.html",
        summary=summary,
        docx_filename=docx_filename,
        followed_links=research.linked_pages,
        provider_used=provider.name,
        generated_at=generated_at,
        section_minutes=_section_minutes(summary),
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
    )


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


def init_db():
    with app.app_context():
        _migrate_role_tag_table()
        db.create_all()
        _migrate_user_table()
        _migrate_system_prompt_scoring_rows_column()
        _migrate_question_table()


if __name__ == "__main__":
    init_db()
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", "5001"))
    app.run(host=host, port=port, debug=debug)
