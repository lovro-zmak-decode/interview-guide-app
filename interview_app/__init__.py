import os
from flask import Flask
from flask_login import LoginManager
from .models import db, User


def create_app(config=None):
    # Get the base directory (parent of interview_app)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    # Required settings. There are no defaults on purpose: a forgotten secret
    # would let anyone forge a login session, and a forgotten database URL would
    # silently start on a different, empty database. Locally they go in .env.
    missing = [name for name in ("FLASK_SECRET_KEY", "DATABASE_URL") if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. Copy .env.example to .env "
            "and fill them in. Generate a secret with: "
            "python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    app.secret_key = os.environ["FLASK_SECRET_KEY"]
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Database configuration
    database_url = os.environ["DATABASE_URL"]
    for prefix in ("postgres://", "postgresql://"):
        if database_url.startswith(prefix):
            # Hosts hand out postgres:// or postgresql://. Name the driver we ship
            # (psycopg2) so a newer SQLAlchemy default driver is never needed.
            database_url = "postgresql+psycopg2://" + database_url[len(prefix):]
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
        # A relative SQLite path means relative to the project folder (not to
        # wherever the app was started, or Flask-SQLAlchemy's instance folder).
        sqlite_path = os.path.join(base_dir, database_url[len("sqlite:///"):])
        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        database_url = "sqlite:///" + sqlite_path
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    # Upload directories (base_dir already defined above)
    upload_dir = os.path.join(base_dir, "uploads")
    generated_dir = os.path.join(base_dir, "generated")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(generated_dir, exist_ok=True)
    app.config["UPLOAD_DIR"] = upload_dir
    app.config["GENERATED_DIR"] = generated_dir

    # Apply custom config if provided
    if config:
        app.config.update(config)

    # Initialize extensions
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Initialize Google OAuth (always available, works with or without credentials)
    try:
        from .google_auth import init_google_oauth, google_bp
        init_google_oauth(app)
        app.register_blueprint(google_bp)
    except ImportError:
        pass  # authlib not installed, Google OAuth disabled

    return app
