import json

import pytest

import app as app_module
from interview_app.models import SystemPrompt, db
from interview_app.prompts import render_prompt_template
from interview_app.schema import (
    InterviewDebrief,
    ScoringRow,
    ensure_baseline_scoring_rows,
    estimate_section_minutes,
    estimate_total_minutes,
)
from interview_app.summarizer import SummaryGenerationError, generate_interview_debrief, generate_interview_summary
from tests.conftest import sample_summary


class Scripted:
    """A model that returns the given replies in order."""

    name = "openai"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0

    def generate(self, system_prompt, user_prompt):
        self.calls += 1
        return self.replies.pop(0)


@pytest.fixture
def prompts(make_prompt):
    return {"technical": make_prompt("technical"), "summary": make_prompt("summary")}


def test_prompt_variables_are_filled_and_other_braces_are_left_alone():
    text = render_prompt_template('Hi {name}. JSON: {"a": 1} and {unknown}', {"name": "Jane"})
    assert text == 'Hi Jane. JSON: {"a": 1} and {unknown}'


def test_a_list_from_the_model_becomes_bullet_points():
    debrief = InterviewDebrief(summary=["One", "Two"], second_round_suggestions=["A"])
    assert debrief.summary == "- One\n- Two" and debrief.second_round_suggestions == "- A"


def test_the_debrief_is_parsed_even_inside_a_code_fence(prompts):
    reply = '```json\n{"summary": "S", "second_round_suggestions": "T"}\n```'
    with app_module.app.app_context():
        debrief = generate_interview_debrief(Scripted(reply), {"candidate_name": "x"})
    assert (debrief.summary, debrief.second_round_suggestions) == ("S", "T")


def test_the_debrief_retries_once_after_invalid_json(prompts):
    model = Scripted("not json at all", json.dumps({"summary": "S"}))
    with app_module.app.app_context():
        assert generate_interview_debrief(model, {}).summary == "S"
    assert model.calls == 2


def test_the_debrief_gives_up_after_two_invalid_replies(prompts):
    model = Scripted("nope", "still nope")
    with app_module.app.app_context(), pytest.raises(SummaryGenerationError, match="two attempts"):
        generate_interview_debrief(model, {})


def test_the_debrief_needs_a_summary_prompt(make_prompt):
    make_prompt("technical")  # a guide prompt is not enough
    with app_module.app.app_context(), pytest.raises(SummaryGenerationError, match="summary"):
        generate_interview_debrief(Scripted("{}"), {})


def test_the_newest_summary_prompt_is_used(prompts):
    with app_module.app.app_context():
        old = db.session.get(SystemPrompt, prompts["summary"])
        old.content = "OLD PROMPT"
        db.session.add(SystemPrompt(name="newer", type="summary", content="NEWER PROMPT {live_notes}", scoring_rows=""))
        db.session.commit()
        old.content = "OLD PROMPT"  # touch the older row first
        db.session.commit()
        newest = max(SystemPrompt.query.filter_by(type="summary"), key=lambda p: p.updated_at)
        seen = []

        class Spy(Scripted):
            def generate(self, system_prompt, user_prompt):
                seen.append(system_prompt)
                return json.dumps({"summary": "S"})

        generate_interview_debrief(Spy(), {"live_notes": "NOTES"})
        assert seen[0].startswith(newest.content.split(" {")[0])


def test_the_guide_generation_needs_a_selected_prompt():
    with app_module.app.app_context(), pytest.raises(SummaryGenerationError, match="No system prompt"):
        generate_interview_summary(Scripted(), "research", "Jane", "Dev", prompt_id=None)


def test_the_guide_generation_retries_once_and_then_fills_missing_baseline_rows(prompts):
    guide_json = sample_summary().model_dump_json()
    with app_module.app.app_context():
        prompt = db.session.get(SystemPrompt, prompts["technical"])
        prompt.scoring_rows = json.dumps([{"area": "Teamwork", "ideal_signs": "Helps others"}])
        db.session.commit()
        model = Scripted("garbage", guide_json)
        summary = generate_interview_summary(model, "research", "Jane", "Dev", prompt_id=prompts["technical"])
    assert model.calls == 2
    assert [row.area for row in summary.scoring_table] == ["Basics", "Communication", "Teamwork"]


def test_baseline_rows_are_added_only_when_missing():
    existing = [ScoringRow(area="React (domain knowledge)", ideal_signs="x")]
    baseline = [
        {"area": "React (domain knowledge)", "ideal_signs": "other"},
        {"area": "Communication", "ideal_signs": "clear"},
    ]
    rows = ensure_baseline_scoring_rows(existing, baseline)
    assert [(r.area, r.ideal_signs) for r in rows] == [("React (domain knowledge)", "x"), ("Communication", "clear")]


def test_time_estimates_follow_the_number_of_questions():
    assert estimate_section_minutes(4) == 12
    summary = sample_summary()  # 5 questions
    assert estimate_total_minutes(summary) == 5 * 3 + 5
