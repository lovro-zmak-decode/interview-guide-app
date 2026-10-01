"""
Shared Questions DB: interview questions visible to (and selectable by) every
logged-in user when generating a guide, but only creatable/editable/deletable
by admins and superadmins. This replaces the old "share this group with the
team" toggle — regular users can no longer share their own groups; only
admins curate what lands in the shared pool. See interview_app.question_bank
for a user's own private groups ("Own Questions DB").
"""

from __future__ import annotations

import os
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from .auth import admin_required
from .docx_generator import build_group_preview_docx
from .models import Question, QuestionGroup, db
from .question_bank_import import parse_question_bank_docx

shared_qb_bp = Blueprint("shared_questions", __name__, url_prefix="/shared-questions")

ALLOWED_IMPORT_EXTENSIONS = {".docx"}


def _get_shared_group_or_404(group_id: int) -> QuestionGroup:
    group = QuestionGroup.query.get_or_404(group_id)
    if not group.is_shared():
        flash("That group isn't part of the Shared Questions DB.")
    return group


@shared_qb_bp.route("/", methods=["GET"])
@admin_required
def list_groups():
    groups = QuestionGroup.shared().all()
    return render_template("shared_questions.html", groups=groups)


@shared_qb_bp.route("/import", methods=["POST"])
@admin_required
def import_docx():
    file = request.files.get("bank_file")

    if not file or file.filename == "":
        flash("Attach a .docx file with questions.")
        return redirect(url_for("shared_questions.list_groups"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMPORT_EXTENSIONS:
        flash("Only .docx format is supported for question bank import.")
        return redirect(url_for("shared_questions.list_groups"))

    upload_dir = current_app.config["UPLOAD_DIR"]
    tmp_path = os.path.join(upload_dir, f"qbank_{uuid.uuid4().hex[:8]}{ext}")
    file.save(tmp_path)

    try:
        parsed_groups = parse_question_bank_docx(tmp_path)
    except Exception as exc:
        flash(f"Failed to read the file: {exc}")
        return redirect(url_for("shared_questions.list_groups"))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not parsed_groups:
        flash("Couldn't find any group/question in the file. Check the format (Heading 2 = group, Heading 3 = question).")
        return redirect(url_for("shared_questions.list_groups"))

    max_position = db.session.query(db.func.max(QuestionGroup.position)).scalar() or 0
    for i, parsed in enumerate(parsed_groups, start=1):
        group = QuestionGroup(
            name=parsed.name,
            visibility="shared",
            owner_id=current_user.id,
            position=max_position + i,
        )
        for j, pq in enumerate(parsed.questions):
            group.questions.append(
                Question(question_text=pq.question_text, explanation=pq.explanation, position=j)
            )
        db.session.add(group)

    db.session.commit()
    flash(f"Imported {len(parsed_groups)} shared question group(s).")
    return redirect(url_for("shared_questions.list_groups"))


@shared_qb_bp.route("/groups", methods=["POST"])
@admin_required
def create_group():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Group name is required.")
        return redirect(url_for("shared_questions.list_groups"))

    max_position = db.session.query(db.func.max(QuestionGroup.position)).scalar() or 0
    group = QuestionGroup(name=name, visibility="shared", owner_id=current_user.id, position=max_position + 1)
    db.session.add(group)
    db.session.commit()
    flash(f"Group '{name}' has been created.")
    return redirect(url_for("shared_questions.list_groups"))


@shared_qb_bp.route("/groups/<int:group_id>/rename", methods=["POST"])
@admin_required
def rename_group(group_id: int):
    group = _get_shared_group_or_404(group_id)
    if not group.is_shared():
        return redirect(url_for("shared_questions.list_groups"))

    new_name = request.form.get("name", "").strip()
    if new_name:
        group.name = new_name
        db.session.commit()
    return redirect(url_for("shared_questions.list_groups"))


@shared_qb_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@admin_required
def delete_group(group_id: int):
    group = _get_shared_group_or_404(group_id)
    if not group.is_shared():
        return redirect(url_for("shared_questions.list_groups"))

    db.session.delete(group)
    db.session.commit()
    flash(f"Group '{group.name}' has been deleted.")
    return redirect(url_for("shared_questions.list_groups"))


@shared_qb_bp.route("/groups/<int:group_id>", methods=["GET"])
@admin_required
def group_detail(group_id: int):
    group = _get_shared_group_or_404(group_id)
    if not group.is_shared():
        return redirect(url_for("shared_questions.list_groups"))
    return render_template("shared_question_group_detail.html", group=group)


@shared_qb_bp.route("/groups/<int:group_id>/preview", methods=["GET"])
@admin_required
def preview_group(group_id: int):
    """Generate a .docx showing exactly how this group's questions (and their
    own explanation text) would be laid out inside a real generated interview
    guide — no LLM call involved, just a rendering preview."""
    group = _get_shared_group_or_404(group_id)
    if not group.is_shared():
        return redirect(url_for("shared_questions.list_groups"))

    if not group.questions:
        flash(f"Group '{group.name}' has no questions to preview yet.")
        return redirect(url_for("shared_questions.list_groups"))

    generated_dir = current_app.config["GENERATED_DIR"]
    filename = f"group_preview_{group.id}_{uuid.uuid4().hex[:8]}.docx"
    path = os.path.join(generated_dir, filename)
    build_group_preview_docx(group.name, group.questions, path)
    return send_file(path, as_attachment=True, download_name=f"{group.name}_preview.docx")


@shared_qb_bp.route("/groups/<int:group_id>/questions", methods=["POST"])
@admin_required
def add_question(group_id: int):
    group = _get_shared_group_or_404(group_id)
    if not group.is_shared():
        return redirect(url_for("shared_questions.list_groups"))

    question_text = request.form.get("question_text", "").strip()
    explanation = request.form.get("explanation", "").strip()
    if not question_text:
        flash("Question text can't be empty.")
        return redirect(url_for("shared_questions.group_detail", group_id=group.id))

    max_position = db.session.query(db.func.max(Question.position)).filter(
        Question.group_id == group.id
    ).scalar() or 0
    db.session.add(
        Question(group_id=group.id, question_text=question_text, explanation=explanation, position=max_position + 1)
    )
    db.session.commit()
    return redirect(url_for("shared_questions.group_detail", group_id=group.id))


@shared_qb_bp.route("/questions/<int:question_id>/edit", methods=["POST"])
@admin_required
def edit_question(question_id: int):
    question = Question.query.get_or_404(question_id)
    if not question.group.is_shared():
        flash("That question isn't part of the Shared Questions DB.")
        return redirect(url_for("shared_questions.list_groups"))

    question_text = request.form.get("question_text", "").strip()
    if question_text:
        question.question_text = question_text
        question.explanation = request.form.get("explanation", "").strip()
        db.session.commit()
    return redirect(url_for("shared_questions.group_detail", group_id=question.group_id))


@shared_qb_bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@admin_required
def delete_question(question_id: int):
    question = Question.query.get_or_404(question_id)
    if not question.group.is_shared():
        flash("That question isn't part of the Shared Questions DB.")
        return redirect(url_for("shared_questions.list_groups"))

    group_id = question.group_id
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for("shared_questions.group_detail", group_id=group_id))
