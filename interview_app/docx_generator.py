"""
Renders an InterviewSummary into a .docx laid out as:

  Title
  Candidate: ... line
  Recommended duration / generated-at date (a real timestamp, not an LLM guess)
  1. Candidate profile and interview goals
  2. Warm-up and experience              (P-numbered questions)
  3. Technical depth                     (Q-numbered quick check, then P-numbered deep dive)
  4. How they think                      (P-numbered questions)
  5. Teamwork and working style          (P-numbered questions)
  6. Candidate questions and wrap-up
  7. Quick evaluation                    (scoring table, filled in right after the interview)

Question numbering: quick-check questions get a "Q" prefix (Q1, Q2, ...), all
other question blocks share a running "P" counter (P1, P2, ...) across
sections 2-5.

Each timed section heading (2-6) also shows a recommended time estimate, e.g.
"2. Warm-up and experience (~9 min)", computed from its question count at
~3 min/question (see schema.MINUTES_PER_QUESTION) — not something the LLM
reports itself, so it always matches the actual number of questions returned.
"""

from __future__ import annotations

from datetime import datetime

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .schema import (
    InterviewSummary,
    InterviewQuestion,
    MINUTES_PER_QUESTION,
    WRAP_UP_MINUTES,
    estimate_section_minutes,
    estimate_total_minutes,
)


def _add_section_heading(doc: Document, text: str, minutes: int | None = None, level: int = 1):
    heading = f"{text} (~{minutes} min)" if minutes is not None else text
    return doc.add_heading(heading, level=level)


def _add_question_block(doc: Document, label: str, item: InterviewQuestion) -> None:
    q_para = doc.add_paragraph()
    q_run = q_para.add_run(f"{label}. {item.question}")
    q_run.bold = True

    guidance_para = doc.add_paragraph(item.guidance)
    guidance_para.paragraph_format.left_indent = Pt(18)

    if item.follow_up:
        fu_para = doc.add_paragraph()
        fu_run = fu_para.add_run(f"Follow-up: {item.follow_up}")
        fu_run.italic = True
        fu_para.paragraph_format.left_indent = Pt(18)


def build_docx(summary: InterviewSummary, output_path: str, generated_at: datetime | None = None) -> str:
    doc = Document()
    generated_at = generated_at or datetime.now()

    title = doc.add_heading(summary.title, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    doc.add_paragraph(f"Candidate: {summary.candidate_name}, {summary.role_title}")
    doc.add_paragraph(
        f"Recommended duration: {summary.duration_minutes} minutes. "
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M')}."
    )
    doc.add_paragraph(
        f"Estimated time for the sections below (~{MINUTES_PER_QUESTION} min/question + wrap-up): "
        f"~{estimate_total_minutes(summary)} min."
    )

    # 1. Candidate profile and interview goals
    doc.add_heading("1. Candidate profile and interview goals", level=1)
    for para in summary.profile_and_goals.split("\n\n"):
        if para.strip():
            doc.add_paragraph(para.strip())

    if summary.interview_goals:
        doc.add_paragraph("What we want to learn in this interview:")
        for goal in summary.interview_goals:
            doc.add_paragraph(goal, style="List Bullet")

    p_counter = 1

    # 2. Warm-up and experience
    _add_section_heading(doc, "2. Warm-up and experience", estimate_section_minutes(len(summary.warmup_questions)))
    for item in summary.warmup_questions:
        _add_question_block(doc, f"P{p_counter}", item)
        p_counter += 1

    # 3. Technical depth
    technical_count = len(summary.quick_check_questions) + len(summary.deep_dive_questions)
    _add_section_heading(doc, "3. Technical depth", estimate_section_minutes(technical_count))
    if summary.quick_check_questions:
        doc.add_heading("Quick fundamentals check", level=2)
        for idx, item in enumerate(summary.quick_check_questions, start=1):
            _add_question_block(doc, f"Q{idx}", item)

    if summary.deep_dive_questions:
        doc.add_heading("Deep-dive questions", level=2)
        for item in summary.deep_dive_questions:
            _add_question_block(doc, f"P{p_counter}", item)
            p_counter += 1

    # 4. How they think
    _add_section_heading(doc, "4. How they think", estimate_section_minutes(len(summary.thinking_questions)))
    for item in summary.thinking_questions:
        _add_question_block(doc, f"P{p_counter}", item)
        p_counter += 1

    # 5. Teamwork and working style
    _add_section_heading(doc, "5. Teamwork and working style", estimate_section_minutes(len(summary.teamwork_questions)))
    for item in summary.teamwork_questions:
        _add_question_block(doc, f"P{p_counter}", item)
        p_counter += 1

    # 6. Candidate questions and wrap-up
    _add_section_heading(doc, "6. Candidate questions and wrap-up", WRAP_UP_MINUTES)
    doc.add_paragraph(
        "Leave time for their questions. Also check on practical things:"
    )
    for note in summary.closing_notes:
        doc.add_paragraph(note, style="List Bullet")

    # 7. Quick evaluation
    doc.add_heading("7. Quick evaluation", level=1)
    doc.add_paragraph("Do immediately after the interview.")
    doc.add_paragraph(
        f"Overall recommendation: {summary.overall_recommendation_scale}"
    )

    if summary.scoring_table:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Area"
        hdr[1].text = "How it looks 5/5"
        hdr[2].text = "Grade"
        hdr[3].text = "Note"
        for row in summary.scoring_table:
            cells = table.add_row().cells
            cells[0].text = row.area
            cells[1].text = row.ideal_signs
            cells[2].text = ""
            cells[3].text = ""

    # Reference appendix — the interviewer's full original Questions DB
    # selection, unnumbered and placed at the very end so it doesn't compete
    # with the timed guide above. The guide's own sections already picked
    # whichever of these fit this candidate and the available time; this
    # list is just here in case it's useful, not something to work through.
    if summary.curated_question_groups:
        doc.add_heading("Additional questions from the Questions DB", level=1)
        doc.add_paragraph(
            "Reference only. These are every question originally selected from the Questions "
            "DB for this guide. The sections above already picked whichever of these (if any) "
            "fit this candidate and the available interview time — nothing here needs to be "
            "asked again unless it's useful."
        )
        b_counter = 1
        for curated in summary.curated_question_groups:
            doc.add_heading(curated.group_name, level=2)
            for item in curated.questions:
                _add_question_block(doc, f"B{b_counter}", item)
                b_counter += 1

    doc.save(output_path)
    return output_path


def build_group_preview_docx(group_name: str, questions: list, output_path: str) -> str:
    """Renders one Questions DB group the same way it would appear inside a real
    generated guide's "Additional questions from the Questions DB" section —
    without calling an LLM. Each question's own `explanation` field (one point
    per line, as edited on the Questions DB page) stands in for the guidance a
    generated guide would otherwise get tailored by the model. Lets a user
    preview the exact layout/wording their imported questions will produce
    before ever spending an LLM call on them.
    `questions` is a list of Question model instances (must have
    `question_text` and `explanation`)."""
    doc = Document()

    title = doc.add_heading(f"Preview: {group_name}", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.add_paragraph(
        "Preview only — shows how this group's questions will be laid out inside a "
        "generated interview guide. The text below each question is this group's own "
        "explanation, shown as-is; a real generated guide tailors it to the candidate instead."
    )

    doc.add_heading(group_name, level=1)
    for idx, q in enumerate(questions, start=1):
        guidance = (q.explanation or "").strip() or "(no explanation provided for this question yet)"
        item = InterviewQuestion(question=q.question_text, guidance=guidance)
        _add_question_block(doc, f"B{idx}", item)

    doc.save(output_path)
    return output_path
