"""
Own Questions DB: each user's private set of interview questions, uploaded as
a docx or added by hand, organized into groups. Always private to its
owner — there's no team-sharing here anymore; for questions the whole team
should be able to use, see interview_app.shared_questions (the admin-managed
"Shared Questions DB").
"""

from __future__ import annotations

import os
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from .docx_generator import build_group_preview_docx
from .models import Question, QuestionGroup, db
from .question_bank_import import parse_question_bank_docx

qb_bp = Blueprint("questions", __name__, url_prefix="/questions")

ALLOWED_IMPORT_EXTENSIONS = {".docx"}


def _get_own_group_or_404(group_id: int) -> QuestionGroup:
    group = QuestionGroup.query.get_or_404(group_id)
    return group


@qb_bp.route("/", methods=["GET"])
@login_required
def list_groups():
    groups = QuestionGroup.own_for(current_user).all()
    return render_template("questions.html", groups=groups)


@qb_bp.route("/import", methods=["POST"])
@login_required
def import_docx():
    file = request.files.get("bank_file")

    if not file or file.filename == "":
        flash("Attach a .docx file with questions.")
        return redirect(url_for("questions.list_groups"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMPORT_EXTENSIONS:
        flash("Only .docx format is supported for question bank import.")
        return redirect(url_for("questions.list_groups"))

    upload_dir = current_app.config["UPLOAD_DIR"]
    tmp_path = os.path.join(upload_dir, f"qbank_{uuid.uuid4().hex[:8]}{ext}")
    file.save(tmp_path)

    try:
        parsed_groups = parse_question_bank_docx(tmp_path)
    except Exception as exc:
        flash(f"Failed to read the file: {exc}")
        return redirect(url_for("questions.list_groups"))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not parsed_groups:
        flash("Couldn't find any group/question in the file. Check the format (Heading 2 = group, Heading 3 = question).")
        return redirect(url_for("questions.list_groups"))

    max_position = db.session.query(db.func.max(QuestionGroup.position)).scalar() or 0
    for i, parsed in enumerate(parsed_groups, start=1):
        group = QuestionGroup(
            name=parsed.name,
            visibility="private",
            owner_id=current_user.id,
            position=max_position + i,
        )
        for j, pq in enumerate(parsed.questions):
            group.questions.append(
                Question(question_text=pq.question_text, explanation=pq.explanation, position=j)
            )
        db.session.add(group)

    db.session.commit()
    flash(f"Imported {len(parsed_groups)} question group(s).")
    return redirect(url_for("questions.list_groups"))


@qb_bp.route("/groups", methods=["POST"])
@login_required
def create_group():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Group name is required.")
        return redirect(url_for("questions.list_groups"))

    max_position = db.session.query(db.func.max(QuestionGroup.position)).scalar() or 0
    group = QuestionGroup(name=name, visibility="private", owner_id=current_user.id, position=max_position + 1)
    db.session.add(group)
    db.session.commit()
    flash(f"Group '{name}' has been created.")
    return redirect(url_for("questions.list_groups"))


@qb_bp.route("/groups/<int:group_id>/rename", methods=["POST"])
@login_required
def rename_group(group_id: int):
    group = _get_own_group_or_404(group_id)
    if not group.can_manage(current_user):
        flash("You don't have permission to edit this group.")
        return redirect(url_for("questions.list_groups"))

    new_name = request.form.get("name", "").strip()
    if new_name:
        group.name = new_name
        db.session.commit()
    return redirect(url_for("questions.list_groups"))


@qb_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id: int):
    group = _get_own_group_or_404(group_id)
    if not group.can_manage(current_user):
        flash("You don't have permission to delete this group.")
        return redirect(url_for("questions.list_groups"))

    db.session.delete(group)
    db.session.commit()
    flash(f"Group '{group.name}' has been deleted.")
    return redirect(url_for("questions.list_groups"))


@qb_bp.route("/groups/<int:group_id>", methods=["GET"])
@login_required
def group_detail(group_id: int):
    group = _get_own_group_or_404(group_id)
    if not group.can_manage(current_user):
        flash("You don't have permission to view this group.")
        return redirect(url_for("questions.list_groups"))
    return render_template("question_group_detail.html", group=group)


@qb_bp.route("/groups/<int:group_id>/preview", methods=["GET"])
@login_required
def preview_group(group_id: int):
    """Generate a .docx showing exactly how this group's questions (and their
    own explanation text) would be laid out inside a real generated interview
    guide — no LLM call involved, just a rendering preview."""
    group = _get_own_group_or_404(group_id)
    if not group.can_manage(current_user):
        flash("You don't have permission to view this group.")
        return redirect(url_for("questions.list_groups"))

    if not group.questions:
        flash(f"Group '{group.name}' has no questions to preview yet.")
        return redirect(url_for("questions.list_groups"))

    generated_dir = current_app.config["GENERATED_DIR"]
    filename = f"group_preview_{group.id}_{uuid.uuid4().hex[:8]}.docx"
    path = os.path.join(generated_dir, filename)
    build_group_preview_docx(group.name, group.questions, path)
    return send_file(path, as_attachment=True, download_name=f"{group.name}_preview.docx")


@qb_bp.route("/groups/<int:group_id>/questions", methods=["POST"])
@login_required
def add_question(group_id: int):
    group = _get_own_group_or_404(group_id)
    if not group.can_manage(current_user):
        flash("You don't have permission to edit this group.")
        return redirect(url_for("questions.list_groups"))

    question_text = request.form.get("question_text", "").strip()
    explanation = request.form.get("explanation", "").strip()
    if not question_text:
        flash("Question text can't be empty.")
        return redirect(url_for("questions.group_detail", group_id=group.id))

    max_position = db.session.query(db.func.max(Question.position)).filter(
        Question.group_id == group.id
    ).scalar() or 0
    db.session.add(
        Question(group_id=group.id, question_text=question_text, explanation=explanation, position=max_position + 1)
    )
    db.session.commit()
    return redirect(url_for("questions.group_detail", group_id=group.id))


@qb_bp.route("/questions/<int:question_id>/edit", methods=["POST"])
@login_required
def edit_question(question_id: int):
    question = Question.query.get_or_404(question_id)
    if not question.group.can_manage(current_user):
        flash("You don't have permission to edit this group.")
        return redirect(url_for("questions.list_groups"))

    question_text = request.form.get("question_text", "").strip()
    if question_text:
        question.question_text = question_text
        question.explanation = request.form.get("explanation", "").strip()
        db.session.commit()
    return redirect(url_for("questions.group_detail", group_id=question.group_id))


@qb_bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@login_required
def delete_question(question_id: int):
    question = Question.query.get_or_404(question_id)
    if not question.group.can_manage(current_user):
        flash("You don't have permission to edit this group.")
        return redirect(url_for("questions.list_groups"))

    group_id = question.group_id
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for("questions.group_detail", group_id=group_id))
