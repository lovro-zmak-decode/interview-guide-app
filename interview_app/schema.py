"""
Structured shape of a generated interview summary.

This mirrors the sections of the reference document (First Interview Guide):
1. Candidate profile and interview goals
2. Warm-up and experience
3. Technical depth (quick fundamentals check + deep-dive questions)
4. How they think
5. Teamwork and working style
6. Candidate questions and wrap-up
7. Quick evaluation (scoring table, filled in by hand right after the interview)

The LLM is asked to return JSON matching this schema, which we then validate
with pydantic and render into the final .docx.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    question: str = Field(..., description="Question addressed to the candidate, in English.")
    guidance: str = Field(
        ...,
        description=(
            "Guidance for the interviewer: why this question is being asked, what a strong "
            "answer sounds like, possible bonus signals, and red flags to watch for. "
            "Free text, can span multiple sentences/lines."
        ),
    )
    follow_up: Optional[str] = Field(
        default=None, description="Optional follow-up question that digs deeper into the topic."
    )


class ScoringRow(BaseModel):
    area: str = Field(..., description="Area being scored, e.g. 'Basics (OOP, REST, SQL)'.")
    ideal_signs: str = Field(..., description="What a 5/5 score looks like for this area.")


class CuratedQuestionGroup(BaseModel):
    group_name: str = Field(..., description="Exact group name from the question bank, unchanged.")
    questions: list[InterviewQuestion] = Field(
        ...,
        description="EVERY question from this group that the interviewer selected, unmodified.",
    )


class InterviewSummary(BaseModel):
    title: str = "First Interview Guide"
    candidate_name: str
    role_title: str
    duration_minutes: int = 60

    profile_and_goals: str = Field(
        ...,
        description=(
            "Summary of the candidate's profile (education, experience, key projects, "
            "technologies) written as a couple of paragraphs, based on the CV, LinkedIn, "
            "and linked pages."
        ),
    )
    interview_goals: list[str] = Field(
        ..., description="List of things we want to learn in this interview (bullet list)."
    )

    warmup_questions: list[InterviewQuestion] = Field(default_factory=list)
    quick_check_questions: list[InterviewQuestion] = Field(
        default_factory=list,
        description="Quick fundamentals check — shorter questions with a clear expected answer.",
    )
    deep_dive_questions: list[InterviewQuestion] = Field(default_factory=list)
    thinking_questions: list[InterviewQuestion] = Field(default_factory=list)
    teamwork_questions: list[InterviewQuestion] = Field(default_factory=list)

    closing_notes: list[str] = Field(
        default_factory=list,
        description=(
            "Practical things to check at the end (notice period, salary expectations, "
            "location/remote setup, motivation for changing jobs) and a reminder to leave "
            "time for the candidate's own questions."
        ),
    )

    scoring_table: list[ScoringRow] = Field(
        default_factory=list,
        description=(
            "Quick evaluation table, filled in by the interviewer right after the interview. "
            "Must always include at least these six areas, in order: Basics (OOP, REST, SQL, or "
            "whatever fundamentals apply), Domain knowledge for the specific role/technology "
            "being interviewed for (name it explicitly, e.g. 'React (domain knowledge)'), "
            "Thinking and applying knowledge, Ownership and self-awareness, Potential and fit, "
            "and Communication. Additional rows may be added if useful, but none of these six "
            "may be left out — see ensure_baseline_scoring_rows, which enforces this as a "
            "safety net even if the model's output is missing one."
        ),
    )
    overall_recommendation_scale: str = "definitely yes / yes / no / definitely not"

    curated_question_groups: list[CuratedQuestionGroup] = Field(
        default_factory=list,
        description=(
            "Always leave this as an empty list. It is NOT part of your output — the "
            "application fills it in automatically after generation, from the interviewer's "
            "original Questions DB selection, as a reference appendix at the end of the "
            "document. Do not reproduce curated pool questions here; if you use one of them "
            "in the guide above, it belongs in warmup_questions/quick_check_questions/"
            "deep_dive_questions/thinking_questions/teamwork_questions instead."
        ),
    )


# JSON schema dict handed to the LLM as part of the prompt (kept separate from
# pydantic's own .model_json_schema() so we can control exactly how verbose it is).
SCHEMA_DESCRIPTION = InterviewSummary.model_json_schema()


# Recommended-time estimates shown next to each guide section, computed here
# in Python (not asked of the LLM) so they're always consistent with the
# actual number of questions the model returned. Matches the "~3 minutes per
# question" rule the system prompt uses when sizing how many questions to
# generate for the given interview duration.
MINUTES_PER_QUESTION = 3
# Sections 1 (candidate profile, prep-only, not live time) and 6 (candidate
# questions and wrap-up) aren't sized by a question count, so wrap-up gets a
# flat estimate instead. Kept short (5 min) since HR-related closing
# questions are typically handled separately by another interviewer.
WRAP_UP_MINUTES = 5


def estimate_section_minutes(question_count: int) -> int:
    return question_count * MINUTES_PER_QUESTION


def estimate_total_minutes(summary: InterviewSummary) -> int:
    """Sum of every timed section's estimate — warm-up, technical depth (quick
    check + deep dive together), how-they-think, teamwork, plus the flat
    wrap-up estimate. Compare this to summary.duration_minutes to sanity-check
    that the guide's question count fits the requested interview length."""
    technical_count = len(summary.quick_check_questions) + len(summary.deep_dive_questions)
    return (
        estimate_section_minutes(len(summary.warmup_questions))
        + estimate_section_minutes(technical_count)
        + estimate_section_minutes(len(summary.thinking_questions))
        + estimate_section_minutes(len(summary.teamwork_questions))
        + WRAP_UP_MINUTES
    )


def _normalize_area_label(area: str) -> str:
    """The part of an area name before any parenthetical qualifier, lowercased
    — e.g. 'React (domain knowledge)' -> 'react', 'Basics (OOP, REST, SQL)' ->
    'basics'. Used only to detect whether the model already produced a row
    covering the same area; never used for display."""
    return area.split("(")[0].strip().lower()


def ensure_baseline_scoring_rows(
    rows: list[ScoringRow], baseline_rows: list[dict]
) -> list[ScoringRow]:
    """Appends any row from `baseline_rows` (already rendered — e.g. the
    active SystemPrompt's configured rows with {role_title} etc. filled in)
    that the model's own scoring_table doesn't already cover. Rows the model
    already produced are kept exactly as-is, never duplicated, modified, or
    reordered — a row only counts as "already covered" if its normalized
    label is a substring match against an existing row's area."""
    rows = list(rows)
    existing_labels = [_normalize_area_label(r.area) for r in rows if r.area]

    for spec in baseline_rows:
        area = (spec.get("area") or "").strip()
        ideal_signs = (spec.get("ideal_signs") or "").strip()
        if not area:
            continue

        label = _normalize_area_label(area)
        already_present = bool(label) and any(
            label in existing or existing in label for existing in existing_labels if existing
        )
        if already_present:
            continue

        rows.append(ScoringRow(area=area, ideal_signs=ideal_signs))

    return rows
