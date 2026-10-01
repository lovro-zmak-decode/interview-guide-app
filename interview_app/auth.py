"""
Authentication: invite-only accounts, identified by email.

There is no public registration form. Two ways an account gets created:
1. Bootstrap: if the database has zero users, anyone can visit /setup once to
   create the first account, which automatically becomes superadmin.
2. Afterwards, only the superadmin can create further accounts, via
   /admin/users.

Three access tiers (see models.User):
- user: generate guides, see their own guide history, manage their own
  Own Questions DB.
- admin: everything a user can, plus managing the Shared Questions DB,
  Interview Roles, and System Prompts.
- superadmin: everything an admin can, plus managing user accounts.

Login/logout use Flask-Login sessions.
"""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .models import User, db

auth_bp = Blueprint("auth", __name__)


def admin_required(view):
    """Admin or superadmin."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            flash("This page is only available to admins.")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


def superadmin_required(view):
    """Superadmin only — currently just user-account management."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_superadmin:
            flash("This page is only available to the superadmin.")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """One-time bootstrap: only usable while there are no users at all. The
    first account created this way always gets full (superadmin) access."""
    if User.query.count() > 0:
        flash("Setup is already done — log in or ask the superadmin for an account.")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("auth.setup"))
        if "@" not in email:
            flash("Enter a valid email address.")
            return redirect(url_for("auth.setup"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for("auth.setup"))

        user = User(email=email, role="superadmin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("The first account has been created, with full (superadmin) access.")
        return redirect(url_for("index"))

    return render_template("setup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if User.query.count() == 0:
        return redirect(url_for("auth.setup"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Incorrect email or password.")
            return redirect(url_for("auth.login"))
        login_user(user)
        next_url = request.args.get("next")
        return redirect(next_url or url_for("index"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/admin/users", methods=["GET"])
@superadmin_required
def manage_users():
    users = User.query.order_by(User.created_at).all()
    return render_template("admin_users.html", users=users)


@auth_bp.route("/admin/users/create", methods=["POST"])
@superadmin_required
def create_user():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")
    if role not in ("user", "admin", "superadmin"):
        role = "user"

    if not email or not password:
        flash("Email and password are required.")
        return redirect(url_for("auth.manage_users"))
    if "@" not in email:
        flash("Enter a valid email address.")
        return redirect(url_for("auth.manage_users"))
    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return redirect(url_for("auth.manage_users"))
    if User.query.filter_by(email=email).first():
        flash(f"'{email}' already has an account.")
        return redirect(url_for("auth.manage_users"))

    user = User(email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"Account for '{email}' has been created.")
    return redirect(url_for("auth.manage_users"))


@auth_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@superadmin_required
def delete_user(user_id: int):
    if user_id == current_user.id:
        flash("You can't delete your own account while logged in.")
        return redirect(url_for("auth.manage_users"))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f"Account for '{user.email}' has been deleted.")
    return redirect(url_for("auth.manage_users"))
