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


def _add_question_block(
    doc: Document, label: str, item: InterviewQuestion, notes: list[tuple[str | None, str]] | None = None
) -> None:
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

    for name, note in notes or []:
        note_para = doc.add_paragraph()
        note_run = note_para.add_run(f"Notes on the answer ({name}): " if name else "Notes on the answer: ")
        note_run.bold = True
        note_para.add_run(note)
        note_para.paragraph_format.left_indent = Pt(18)


def _add_interview_outcome(doc: Document, log: dict, name: str | None = None) -> None:
    """Summary, second-round choice and suggestions, placed at the very top of
    a report that has interview notes. The labels are Croatian because the
    summary itself is written in the language of the interview."""
    summary = log.get("summary")
    if not (summary or log.get("second_round")):
        return

    heading = "Sažetak razgovora" + (f" ({name})" if name else "")
    if summary and not summary.get("reviewed"):
        heading += " (nacrt, nije pregledano)"
    doc.add_heading(heading, level=1)

    if summary:
        for para in (summary.get("summary") or "").split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip())

    choice = log.get("second_round") or "DA / NE"
    rec = doc.add_paragraph()
    rec.add_run("Preporuka za drugi krug: ").bold = True
    rec.add_run(choice)

    if summary:
        sug = doc.add_paragraph()
        sug.add_run("Prijedlozi za dodatna pitanja na 2. krugu, napomene i sl.:").bold = True
        for line in (summary.get("second_round_suggestions") or "").split("\n"):
            if line.strip():
                doc.add_paragraph(line.strip().lstrip("-* ").strip(), style="List Bullet")


def build_docx(
    summary: InterviewSummary,
    output_path,
    generated_at: datetime | None = None,
    logs: list[dict] | None = None,
) -> str:
    """`output_path` may be a path or a file-like object. `logs` holds each
    interviewer's notes (see interview_app.interview_log) plus a "name"; when
    given, the report also contains their summaries, per-question notes, live
    notes and the filled-in evaluation. Names are only printed when more than
    one person took notes."""
    doc = Document()
    generated_at = generated_at or datetime.now()
    logs = logs or []
    multi = len(logs) > 1
    scorers = [l for l in logs if l.get("evaluation") or l.get("recommendation") or l.get("summary") or l.get("second_round")]

    def who(log: dict) -> str | None:
        return log.get("name") if multi else None

    def who_scoring(log: dict) -> str | None:
        return log.get("name") if len(scorers) > 1 else None

    def notes_for(key: str) -> list[tuple[str | None, str]]:
        return [(who(l), l["answers"][key]) for l in logs if l.get("answers", {}).get(key)]

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

    for log in scorers:
        _add_interview_outcome(doc, log, who_scoring(log))

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
    for i, item in enumerate(summary.warmup_questions):
        _add_question_block(doc, f"P{p_counter}", item, notes_for(f"warmup:{i}"))
        p_counter += 1

    # 3. Technical depth
    technical_count = len(summary.quick_check_questions) + len(summary.deep_dive_questions)
    _add_section_heading(doc, "3. Technical depth", estimate_section_minutes(technical_count))
    if summary.quick_check_questions:
        doc.add_heading("Quick fundamentals check", level=2)
        for idx, item in enumerate(summary.quick_check_questions, start=1):
            _add_question_block(doc, f"Q{idx}", item, notes_for(f"quick:{idx - 1}"))

    if summary.deep_dive_questions:
        doc.add_heading("Deep-dive questions", level=2)
        for i, item in enumerate(summary.deep_dive_questions):
            _add_question_block(doc, f"P{p_counter}", item, notes_for(f"deep:{i}"))
            p_counter += 1

    # 4. How they think
    _add_section_heading(doc, "4. How they think", estimate_section_minutes(len(summary.thinking_questions)))
    for i, item in enumerate(summary.thinking_questions):
        _add_question_block(doc, f"P{p_counter}", item, notes_for(f"thinking:{i}"))
        p_counter += 1

    # 5. Teamwork and working style
    _add_section_heading(doc, "5. Teamwork and working style", estimate_section_minutes(len(summary.teamwork_questions)))
    for i, item in enumerate(summary.teamwork_questions):
        _add_question_block(doc, f"P{p_counter}", item, notes_for(f"teamwork:{i}"))
        p_counter += 1

    # 6. Candidate questions and wrap-up
    _add_section_heading(doc, "6. Candidate questions and wrap-up", WRAP_UP_MINUTES)
    doc.add_paragraph(
        "Leave time for their questions. Also check on practical things:"
    )
    for note in summary.closing_notes:
        doc.add_paragraph(note, style="List Bullet")

    for log in logs:
        if (log.get("live_notes") or "").strip():
            doc.add_heading("Interview notes" + (f" ({who(log)})" if who(log) else ""), level=1)
            for line in log["live_notes"].strip().split("\n"):
                doc.add_paragraph(line)

    # 7. Quick evaluation
    doc.add_heading("7. Quick evaluation", level=1)
    doc.add_paragraph("Do immediately after the interview.")
    recommendations = [(who_scoring(l), l["recommendation"]) for l in logs if l.get("recommendation")]
    if recommendations:
        for name, value in recommendations:
            doc.add_paragraph(f"Overall recommendation{f' ({name})' if name else ''}: {value}")
    else:
        doc.add_paragraph(f"Overall recommendation: {summary.overall_recommendation_scale}")

    if summary.scoring_table:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Area"
        hdr[1].text = "How it looks 5/5"
        hdr[2].text = "Grade"
        hdr[3].text = "Note"
        for idx, row in enumerate(summary.scoring_table):
            grades, notes = [], []
            for log in logs:
                entry = log.get("evaluation", {}).get(str(idx), {})
                prefix = f"{who_scoring(log)}: " if who_scoring(log) else ""
                if entry.get("grade"):
                    grades.append(f"{prefix}{entry['grade']}/5")
                if entry.get("note"):
                    notes.append(f"{prefix}{entry['note']}")
            cells = table.add_row().cells
            cells[0].text = row.area
            cells[1].text = row.ideal_signs
            cells[2].text = "\n".join(grades)
            cells[3].text = "\n".join(notes)

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
