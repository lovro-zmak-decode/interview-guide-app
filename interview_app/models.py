"""
Database models.

- User: app accounts, identified by email (not username). Accounts are
  invite-only — there is no public self-registration route. Every user has a
  `role`: "user", "admin", or "superadmin" (see interview_app.auth for what
  each level can access).
- QuestionGroup / Question: interview questions. A group is either "private"
  (a user's own "Own Questions DB" — only its owner can see/edit it) or
  "shared" (the "Shared Questions DB" — every logged-in user can see it and
  select its questions when generating a guide, but only admins/superadmins
  can create, edit, or delete it).
- GeneratedGuide: one generated interview guide, private to the user who
  generated it.
- InterviewRole: a reusable "interview role" tag offered on the generate form
  (e.g. "Backend Developer"). Global and flat; anyone can add a new one by
  typing it on the generate form, but the management page is admin-only.
- SystemPrompt: a DB-stored prompt template sent to the LLM. See
  interview_app.prompts.PROMPT_VARIABLES for the placeholders its `content`
  may reference.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ROLES = ("user", "admin", "superadmin")


class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    question_groups = db.relationship(
        "QuestionGroup", backref="owner", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        """True for both admin and superadmin — the "can manage shared
        resources" tier."""
        return self.role in ("admin", "superadmin")

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"


class QuestionGroup(db.Model):
    __tablename__ = "question_group"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    visibility = db.Column(db.String(20), nullable=False, default="private")  # 'private' | 'shared'
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    questions = db.relationship(
        "Question",
        backref="group",
        cascade="all, delete-orphan",
        order_by="Question.position",
    )

    def is_shared(self) -> bool:
        return self.visibility == "shared"

    def can_manage(self, user: "User") -> bool:
        """Whether `user` may rename/delete this group, or add/edit/remove its
        questions. Shared ("Shared Questions DB") groups are admin-managed
        only; private groups ("Own Questions DB") are owner-only."""
        if self.is_shared():
            return user.is_admin
        return self.owner_id == user.id

    @staticmethod
    def visible_to(user: "User"):
        """Groups selectable when generating a guide: the shared DB, plus the
        user's own private groups."""
        return QuestionGroup.query.filter(
            db.or_(QuestionGroup.visibility == "shared", QuestionGroup.owner_id == user.id)
        ).order_by(QuestionGroup.position, QuestionGroup.id)

    @staticmethod
    def own_for(user: "User"):
        return QuestionGroup.query.filter_by(owner_id=user.id, visibility="private").order_by(
            QuestionGroup.position, QuestionGroup.id
        )

    @staticmethod
    def shared():
        return QuestionGroup.query.filter_by(visibility="shared").order_by(
            QuestionGroup.position, QuestionGroup.id
        )


class Question(db.Model):
    """A single interview question. `question_text` is the question itself —
    the only part shown anywhere it's used to generate a guide (the picker on
    the generate form, the prompt sent to the LLM). `explanation` is optional
    interviewer-facing detail/guidance for the question, stored as one point
    per line — on the Questions DB pages it's edited as a multi-line textarea,
    each line/point its own row."""

    __tablename__ = "question"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("question_group.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=False, default="")
    position = db.Column(db.Integer, default=0)


class GeneratedGuide(db.Model):
    """One generated interview guide. Private to the user who generated it —
    this is a personal history, not a shared team resource like the question
    bank. Keeps the full structured summary (as JSON) so it can be re-viewed
    on the results page later, plus a pointer to the .docx file on disk."""

    __tablename__ = "generated_guide"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    candidate_name = db.Column(db.String(255), nullable=False)
    role_title = db.Column(db.String(255), nullable=False)
    provider_used = db.Column(db.String(50))
    docx_filename = db.Column(db.String(255), nullable=False)
    summary_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("generated_guides", cascade="all, delete-orphan"))

    @staticmethod
    def list_for(user: "User"):
        return GeneratedGuide.query.filter_by(user_id=user.id).order_by(
            GeneratedGuide.created_at.desc()
        )

    @staticmethod
    def list_all():
        """Every generated guide across every user, most recent first — the
        "All guides" admin page. Unlike list_for(), not scoped to one user."""
        return GeneratedGuide.query.order_by(GeneratedGuide.created_at.desc())


class InterviewRole(db.Model):
    """A reusable "interview role" tag offered on the generate form (e.g.
    'Backend Developer'). Global and flat, not per-user like the question
    bank: anyone logged in can add a new one (by typing it on the generate
    form, or from the Interview Roles page), but managing the list (viewing
    the table, deleting entries) is admin/superadmin only.
    """

    __tablename__ = "interview_role"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def all_sorted():
        return InterviewRole.query.order_by(InterviewRole.name).all()

    @staticmethod
    def get_or_create(name: str) -> "InterviewRole":
        """Case-insensitive lookup; creates the tag if it doesn't exist yet."""
        name = name.strip()
        existing = InterviewRole.query.filter(db.func.lower(InterviewRole.name) == name.lower()).first()
        if existing:
            return existing
        tag = InterviewRole(name=name)
        db.session.add(tag)
        db.session.commit()
        return tag


class SystemPrompt(db.Model):
    """A system prompt template sent to the LLM when generating a guide.
    `content` may reference variables like {candidate_name} which get filled
    in at generation time — see interview_app.prompts.PROMPT_VARIABLES for the
    full, authoritative list of what's available. `type` groups prompts by
    purpose; currently only "technical" (the interview-guide prompt) exists,
    but the field exists so more prompt types can be added later without a
    schema change. The interviewer must pick a prompt on the generate form —
    there is no fallback, so generation fails with a clear error if none is
    selected (or the selected one has since been deleted).

    `scoring_rows` is a second, separate prop of the prompt: a JSON list of
    {"area", "ideal_signs"} dicts describing the guaranteed rows of the
    "Quick evaluation" table at the end of every generated guide. Each row's
    text may reference the same {variables} as `content`. The table's columns
    are fixed in code (Area, How it looks 5/5, Grade, Note) — only the rows
    are configurable, read only from this column (see get_scoring_rows()); if
    left empty, no rows are enforced beyond whatever the model itself returns.
    """

    __tablename__ = "system_prompt"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="technical")
    content = db.Column(db.Text, nullable=False, default="")
    scoring_rows = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def all_sorted():
        return SystemPrompt.query.order_by(SystemPrompt.type, SystemPrompt.name).all()

    def get_scoring_rows(self) -> list[dict]:
        """Parsed, unrendered scoring-row templates (may contain {role_title}
        etc.), read only from this prompt's own `scoring_rows` column — no
        hardcoded source-code fallback. Returns an empty list if it's blank
        or not valid JSON, meaning no baseline rows get enforced beyond
        whatever the model's own scoring_table already contains."""
        import json

        if self.scoring_rows and self.scoring_rows.strip():
            try:
                parsed = json.loads(self.scoring_rows)
                if isinstance(parsed, list):
                    return parsed
            except (ValueError, TypeError):
                pass
        return []
