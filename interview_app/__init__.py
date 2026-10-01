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

    # Default configuration
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Database configuration
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Render or production: use PostgreSQL
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        # Local development: use SQLite
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(data_dir, "app.db")

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

    # Initialize Google OAuth (optional - only if configured)
    try:
        if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
            from .google_auth import init_google_oauth, google_bp
            init_google_oauth(app)
            app.register_blueprint(google_bp)
    except ImportError:
        pass  # authlib not installed, Google OAuth disabled

    return app
