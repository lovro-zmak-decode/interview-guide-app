"""Google OAuth authentication using Authlib."""

import os
from authlib.integrations.flask_client import OAuth
from flask import Flask, Blueprint, redirect, url_for, session
from .models import User, db

oauth = OAuth()
google_bp = Blueprint("google_auth", __name__, url_prefix="/auth/google")


def init_google_oauth(app: Flask):
    """Initialize Google OAuth with Flask app."""
    oauth.init_app(app)

    # Only configure if credentials are available
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


@google_bp.route("/login")
def login():
    """Redirect to Google OAuth login."""
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", url_for("google_auth.callback", _external=True))
    return oauth.google.authorize_redirect(redirect_uri)


@google_bp.route("/callback")
def callback():
    """Handle Google OAuth callback."""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo")

        if not user_info:
            return redirect(url_for("auth.login"))

        email = user_info.get("email", "").lower().strip()
        if not email:
            return redirect(url_for("auth.login"))

        # Find or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            # Auto-create user with basic role
            user = User(email=email, role="user")
            user.set_password(email)  # Dummy password (won't be used with OAuth)
            db.session.add(user)
            db.session.commit()

        # Log in the user
        from flask_login import login_user
        login_user(user)

        return redirect(url_for("index"))

    except Exception as e:
        print(f"Google OAuth error: {e}")
        return redirect(url_for("auth.login"))
