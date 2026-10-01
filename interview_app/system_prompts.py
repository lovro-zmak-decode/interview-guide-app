"""
System Prompts: DB-stored templates sent to the LLM when generating a guide.
Each has a `type` (currently only "technical" — the interview-guide
generation prompt), free-form `content` that may reference variables like
{candidate_name} — see PROMPT_VARIABLES in interview_app.prompts for the
full, authoritative list of what's available and what each one means — and a
second prop, `scoring_rows`: the guaranteed rows of the "Quick evaluation"
table at the end of every generated guide (its columns are fixed in code;
only the rows are configurable here, and row text may use the same
variables). The interviewer picks which prompt to use per guide on the
generate form — there is no fallback (see interview_app.summarizer):
generation fails with a clear error if none is picked or the chosen one was
since deleted. Admin/superadmin only.
"""

from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import admin_required
from .models import SystemPrompt, db
from .prompts import PROMPT_VARIABLES


system_prompts_bp = Blueprint("system_prompts", __name__, url_prefix="/system-prompts")


def _scoring_rows_from_form() -> str:
    """Reads the parallel row_area[] / row_ideal_signs[] form arrays posted by
    the rows editor on the edit page and packs them into the JSON string
    stored in SystemPrompt.scoring_rows. Rows with a blank area are dropped."""
    areas = request.form.getlist("row_area")
    ideal_signs_list = request.form.getlist("row_ideal_signs")
    rows = []
    for area, ideal_signs in zip(areas, ideal_signs_list):
        area = area.strip()
        if area:
            rows.append({"area": area, "ideal_signs": ideal_signs.strip()})
    return json.dumps(rows, ensure_ascii=False) if rows else ""


@system_prompts_bp.route("/", methods=["GET"])
@admin_required
def list_prompts():
    prompts = SystemPrompt.all_sorted()
    return render_template("system_prompts.html", prompts=prompts)


@system_prompts_bp.route("/", methods=["POST"])
@admin_required
def create_prompt():
    name = request.form.get("name", "").strip()
    prompt_type = request.form.get("type", "").strip() or "technical"
    if not name:
        flash("Name is required.")
        return redirect(url_for("system_prompts.list_prompts"))

    prompt = SystemPrompt(name=name, type=prompt_type, content="", scoring_rows="")
    db.session.add(prompt)
    db.session.commit()
    flash(f"Created '{name}'. Add its content below.")
    return redirect(url_for("system_prompts.edit_prompt", prompt_id=prompt.id))


@system_prompts_bp.route("/<int:prompt_id>", methods=["GET"])
@admin_required
def edit_prompt(prompt_id: int):
    prompt = SystemPrompt.query.get_or_404(prompt_id)
    return render_template(
        "system_prompt_edit.html",
        prompt=prompt,
        variables=PROMPT_VARIABLES,
        scoring_rows=prompt.get_scoring_rows(),
    )


@system_prompts_bp.route("/<int:prompt_id>", methods=["POST"])
@admin_required
def update_prompt(prompt_id: int):
    prompt = SystemPrompt.query.get_or_404(prompt_id)

    name = request.form.get("name", "").strip()
    prompt_type = request.form.get("type", "").strip()
    if not name or not prompt_type:
        flash("Name and type are required.")
        return redirect(url_for("system_prompts.edit_prompt", prompt_id=prompt.id))

    prompt.name = name
    prompt.type = prompt_type
    prompt.content = request.form.get("content", "")
    prompt.scoring_rows = _scoring_rows_from_form()
    db.session.commit()
    flash("Prompt saved.")
    return redirect(url_for("system_prompts.edit_prompt", prompt_id=prompt.id))


@system_prompts_bp.route("/<int:prompt_id>/delete", methods=["POST"])
@admin_required
def delete_prompt(prompt_id: int):
    prompt = SystemPrompt.query.get_or_404(prompt_id)
    db.session.delete(prompt)
    db.session.commit()
    flash(f"Deleted '{prompt.name}'.")
    return redirect(url_for("system_prompts.list_prompts"))
