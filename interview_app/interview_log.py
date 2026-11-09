"""
Helpers for a user's interview notes on a guide (see models.InterviewLog).

`data_json` holds one JSON object:

    answers          {"warmup:0": "text", ...}   notes per question, keyed by section:index
    live_notes       free-form notes taken during the interview
    evaluation       {"0": {"grade": "4", "note": "..."}}   keyed by Quick evaluation row index
    recommendation   the interviewer's overall recommendation (one of the guide's scale options)
    second_round     "DA", "NE" or "" (only ever set by the interviewer, never by the model)
    summary          None, or {"summary", "second_round_suggestions", "reviewed", "generated_at"}

Question keys use the section and position in the stored guide, which never
changes after generation, so they stay stable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .schema import InterviewSummary

QUESTION_SECTIONS = [
    ("warmup", "warmup_questions", "Warm-up and experience"),
    ("quick", "quick_check_questions", "Quick fundamentals check"),
    ("deep", "deep_dive_questions", "Deep-dive questions"),
    ("thinking", "thinking_questions", "How they think"),
    ("teamwork", "teamwork_questions", "Teamwork and working style"),
]

GRADES = {"1", "2", "3", "4", "5"}
SECOND_ROUND_CHOICES = {"DA", "NE"}
MAX_FIELD_CHARS = 20_000
MAX_BODY_BYTES = 200_000


def empty_data() -> dict:
    return {
        "answers": {},
        "live_notes": "",
        "evaluation": {},
        "recommendation": "",
        "second_round": "",
        "summary": None,
    }


def parse_data(raw: str | None) -> dict:
    data = empty_data()
    try:
        loaded = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return data
    if isinstance(loaded, dict):
        data.update({k: v for k, v in loaded.items() if k in data})
    return data


def recommendation_options(summary: InterviewSummary) -> list[str]:
    return [part.strip() for part in summary.overall_recommendation_scale.split("/") if part.strip()]


def question_keys(summary: InterviewSummary) -> set[str]:
    return {
        f"{key}:{i}"
        for key, attr, _ in QUESTION_SECTIONS
        for i in range(len(getattr(summary, attr)))
    }


def _text(value, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    if len(value) > MAX_FIELD_CHARS:
        raise ValueError(f"{field} is too long")
    return value


def merge_update(data: dict, payload: dict, summary: InterviewSummary) -> dict:
    """Applies a partial update from the page to `data` and returns it. Only
    the fields present in `payload` change; answers and evaluation rows are
    merged key by key. Raises ValueError on anything invalid."""
    valid_keys = question_keys(summary)

    if "answers" in payload:
        answers = payload["answers"]
        if not isinstance(answers, dict):
            raise ValueError("answers must be an object")
        for key, value in answers.items():
            if key not in valid_keys:
                raise ValueError(f"unknown question: {key}")
            text = _text(value, "answer").strip()
            if text:
                data["answers"][key] = text
            else:
                data["answers"].pop(key, None)

    if "live_notes" in payload:
        data["live_notes"] = _text(payload["live_notes"], "live_notes")

    if "evaluation" in payload:
        evaluation = payload["evaluation"]
        if not isinstance(evaluation, dict):
            raise ValueError("evaluation must be an object")
        for idx, row in evaluation.items():
            if not (idx.isdigit() and int(idx) < len(summary.scoring_table)):
                raise ValueError(f"unknown evaluation row: {idx}")
            if not isinstance(row, dict):
                raise ValueError("evaluation row must be an object")
            current = dict(data["evaluation"].get(idx, {}))
            if "grade" in row:
                grade = str(row["grade"]).strip()
                if grade and grade not in GRADES:
                    raise ValueError("grade must be 1 to 5")
                current["grade"] = grade
            if "note" in row:
                current["note"] = _text(row["note"], "note")
            data["evaluation"][idx] = current

    if "recommendation" in payload:
        value = _text(payload["recommendation"], "recommendation").strip()
        if value and value not in recommendation_options(summary):
            raise ValueError("unknown recommendation")
        data["recommendation"] = value

    if "second_round" in payload:
        value = _text(payload["second_round"], "second_round").strip()
        if value and value not in SECOND_ROUND_CHOICES:
            raise ValueError("second_round must be DA or NE")
        data["second_round"] = value

    if "summary_edit" in payload:
        edit = payload["summary_edit"]
        if not isinstance(edit, dict) or not isinstance(data.get("summary"), dict):
            raise ValueError("there is no summary to edit")
        if "summary" in edit:
            data["summary"]["summary"] = _text(edit["summary"], "summary")
        if "second_round_suggestions" in edit:
            data["summary"]["second_round_suggestions"] = _text(
                edit["second_round_suggestions"], "second_round_suggestions"
            )
        if "reviewed" in edit:
            data["summary"]["reviewed"] = bool(edit["reviewed"])

    return data


def has_content(data: dict) -> bool:
    return bool(
        data["answers"]
        or data["live_notes"].strip()
        or data["recommendation"]
        or data["second_round"]
        or data["summary"]
        or any(r.get("grade") or r.get("note") for r in data["evaluation"].values())
    )


def store_summary(data: dict, summary_text: str, suggestions: str) -> None:
    data["summary"] = {
        "summary": summary_text,
        "second_round_suggestions": suggestions,
        "reviewed": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def questions_and_answers_text(summary: InterviewSummary, answers: dict) -> str:
    blocks = []
    for key, attr, label in QUESTION_SECTIONS:
        questions = getattr(summary, attr)
        if not questions:
            continue
        lines = [f"## {label}"]
        for i, q in enumerate(questions):
            note = answers.get(f"{key}:{i}", "").strip()
            lines.append(f"{i + 1}. Question: {q.question}")
            lines.append(f"   Guidance for the interviewer: {q.guidance}")
            lines.append(f"   Interviewer's notes on the answer: {note or '(no notes)'}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) or "(no questions)"


def evaluation_text(summary: InterviewSummary, evaluation: dict) -> str:
    lines = []
    for i, row in enumerate(summary.scoring_table):
        entry = evaluation.get(str(i), {})
        grade = entry.get("grade")
        note = (entry.get("note") or "").strip()
        line = f"- {row.area}: " + (f"{grade}/5" if grade else "not graded")
        if note:
            line += f" ({note})"
        lines.append(line)
    return "\n".join(lines) or "(no evaluation rows)"
