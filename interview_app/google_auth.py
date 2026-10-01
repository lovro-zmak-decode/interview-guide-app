"""Google OAuth authentication using Authlib."""

import os
import logging
from authlib.integrations.flask_client import OAuth
from flask import Flask, Blueprint, redirect, url_for, flash
from flask_login import login_user
from .models import User, db

logger = logging.getLogger(__name__)

oauth = OAuth()
google_bp = Blueprint("google_auth", __name__, url_prefix="/auth/google")


def init_google_oauth(app: Flask):
    """Initialize Google OAuth with Flask app."""
    oauth.init_app(app)

    # Only configure if credentials are available
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if client_id and client_secret:
        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
        logger.info("Google OAuth configured successfully")
    else:
        logger.debug("Google OAuth credentials not configured")


@google_bp.route("/login")
def login():
    """Redirect to Google OAuth login."""
    try:
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", url_for("google_auth.callback", _external=True))
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception as e:
        logger.error(f"Google OAuth login redirect failed: {e}")
        flash("Google sign-in is not configured. Please use email/password login.")
        return redirect(url_for("auth.login"))


@google_bp.route("/callback")
def callback():
    """Handle Google OAuth callback and create/login user."""
    try:
        # Get the access token and user info from Google
        token = oauth.google.authorize_access_token()

        if not token:
            logger.warning("No token received from Google")
            flash("Authentication failed. Please try again.")
            return redirect(url_for("auth.login"))

        # Extract user info from the token
        user_info = token.get("userinfo")

        if not user_info:
            logger.warning("No user info in token from Google")
            flash("Could not retrieve your profile information. Please try again.")
            return redirect(url_for("auth.login"))

        # Validate email
        email = user_info.get("email", "").lower().strip()
        if not email:
            logger.warning(f"No email in user info: {user_info}")
            flash("Your Google account must have a verified email address.")
            return redirect(url_for("auth.login"))

        # Get or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            # Auto-create user with basic role
            try:
                user = User(email=email, role="user")
                user.set_password(email)  # Dummy password (OAuth doesn't use passwords)
                db.session.add(user)
                db.session.commit()
                logger.info(f"Auto-created user from Google OAuth: {email}")
            except Exception as e:
                logger.error(f"Failed to create user from Google OAuth: {e}")
                db.session.rollback()
                flash("Failed to create account. Please contact an administrator.")
                return redirect(url_for("auth.login"))

        # Log in the user
        login_user(user)
        logger.info(f"User logged in via Google OAuth: {email}")

        return redirect(url_for("index"))

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        flash("Authentication failed. Please try again or use email/password login.")
        return redirect(url_for("auth.login"))
