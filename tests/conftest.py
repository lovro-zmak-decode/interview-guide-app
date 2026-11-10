"""
Shared test setup.

The app object is created when `app.py` is imported, so the required settings
are put in the environment first. Tests use a throwaway SQLite file by default;
set TEST_DATABASE_URL to run the same tests against another database
(CI also runs them against PostgreSQL).
"""

from __future__ import annotations

import json
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="interview-tests-")
os.environ["FLASK_SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP_DIR}/test.db"
os.environ.pop("FILE_STORAGE", None)

import pytest  # noqa: E402

import app as app_module  # noqa: E402
from interview_app.models import GeneratedGuide, SystemPrompt, User, db  # noqa: E402
from interview_app.schema import InterviewQuestion, InterviewSummary, ScoringRow  # noqa: E402

DEBRIEF_SUMMARY = "SUMMARY_TEXT"


def sample_summary(**overrides) -> InterviewSummary:
    """A small guide with one question in every section and two evaluation rows."""
    data = {
        "candidate_name": "Jane Doe",
        "role_title": "Backend Developer",
        "profile_and_goals": "Experienced developer.",
        "interview_goals": ["Check the basics"],
        "warmup_questions": [InterviewQuestion(question="Warm-up question?", guidance="Warm-up guidance")],
        "quick_check_questions": [InterviewQuestion(question="Quick question?", guidance="Quick guidance")],
        "deep_dive_questions": [InterviewQuestion(question="Deep question?", guidance="Deep guidance")],
        "thinking_questions": [InterviewQuestion(question="Thinking question?", guidance="Thinking guidance")],
        "teamwork_questions": [InterviewQuestion(question="Teamwork question?", guidance="Teamwork guidance")],
        "scoring_table": [
            ScoringRow(area="Basics", ideal_signs="Solid fundamentals"),
            ScoringRow(area="Communication", ideal_signs="Clear and calm"),
        ],
    }
    data.update(overrides)
    return InterviewSummary(**data)


class StubProvider:
    """Stands in for the language model: records what it was asked."""

    name = "openai"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if "Write the interview summary" in user_prompt:
            return json.dumps({"summary": DEBRIEF_SUMMARY, "second_round_suggestions": ["Ask A", "Ask B"]})
        return sample_summary().model_dump_json()


@pytest.fixture(autouse=True)
def fresh_database():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
    yield
    with app_module.app.app_context():
        db.session.remove()


@pytest.fixture
def llm(monkeypatch) -> StubProvider:
    stub = StubProvider()
    monkeypatch.setattr(app_module, "get_provider", lambda name=None: stub)
    return stub


@pytest.fixture
def make_user():
    def _make(email: str, role: str = "user") -> int:
        with app_module.app.app_context():
            user = User(email=email, role=role)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            return user.id

    return _make


@pytest.fixture
def login():
    def _login(user_id: int):
        client = app_module.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        return client

    return _login


@pytest.fixture
def make_guide():
    def _make(owner_id: int, **overrides) -> int:
        summary = overrides.pop("summary", None) or sample_summary()
        with app_module.app.app_context():
            guide = GeneratedGuide(
                user_id=owner_id,
                candidate_name=summary.candidate_name,
                role_title=summary.role_title,
                provider_used="openai",
                docx_filename=overrides.pop("docx_filename", f"interview_guide_{owner_id:08x}.docx"),
                summary_json=summary.model_dump_json(),
                **overrides,
            )
            db.session.add(guide)
            db.session.commit()
            return guide.id

    return _make


@pytest.fixture
def make_prompt():
    def _make(prompt_type: str = "technical", content: str | None = None) -> int:
        default = {
            "technical": "Write a guide for {candidate_name}.\n{research_text}\n{curated_questions_block}\n{additional_notes}",
            "summary": "Summarise.\n{questions_and_answers}\n{live_notes}\n{evaluation}\n{overall_recommendation}",
        }
        with app_module.app.app_context():
            prompt = SystemPrompt(
                name=f"{prompt_type} prompt", type=prompt_type, content=content or default[prompt_type], scoring_rows=""
            )
            db.session.add(prompt)
            db.session.commit()
            return prompt.id

    return _make
