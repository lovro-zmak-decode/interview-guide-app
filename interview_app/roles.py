"""
Interview Roles: a small, shared list of interview role names (e.g. "Backend
Developer") offered as suggestions on the generate form. Flat and global, not
per-user — but management (adding/removing entries here) is admin/superadmin
only. Any user typing a new role on the generate form still gets it
registered automatically (see app.py's generate() route) so the list grows
from real usage even though only admins can curate it directly.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import admin_required
from .models import InterviewRole, db

roles_bp = Blueprint("roles", __name__, url_prefix="/roles")


@roles_bp.route("/", methods=["GET"])
@admin_required
def list_roles():
    tags = InterviewRole.all_sorted()
    return render_template("roles.html", tags=tags)


@roles_bp.route("/", methods=["POST"])
@admin_required
def create_role():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Interview role name is required.")
        return redirect(url_for("roles.list_roles"))

    existing = InterviewRole.query.filter(db.func.lower(InterviewRole.name) == name.lower()).first()
    if existing:
        flash(f"'{existing.name}' is already in the list.")
        return redirect(url_for("roles.list_roles"))

    db.session.add(InterviewRole(name=name))
    db.session.commit()
    flash(f"Added '{name}'.")
    return redirect(url_for("roles.list_roles"))


@roles_bp.route("/<int:tag_id>/delete", methods=["POST"])
@admin_required
def delete_role(tag_id: int):
    tag = InterviewRole.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    flash(f"Removed '{tag.name}'.")
    return redirect(url_for("roles.list_roles"))
