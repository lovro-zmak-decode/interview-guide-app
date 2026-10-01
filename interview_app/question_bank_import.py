"""
Parses an uploaded .docx into groups of questions.

Convention (documented in the question-bank UI too):
- A "Heading 2" paragraph starts a new GROUP, named after that heading's text.
- A "Heading 3" paragraph starts a new QUESTION within the current group —
  its text becomes the question's question_text.
- Any plain (non-heading) paragraphs between one Heading 3 and the next
  become that question's explanation: each such paragraph is one "point",
  stored as its own line, and later edited as a multi-line note.
- Leading numbering/bullets ("1.", "1)", "P3.", "O7.", "-", "*", "•", ...) are
  stripped from question text and explanation points since python-docx
  already strips real Word bullet characters from list paragraphs — this
  only cleans up plain-text numbering typed by hand.
- A Heading 3 (question) appearing before any Heading 2 falls into an
  implicit "Imported questions" group so nothing gets silently lost.
- Plain paragraphs appearing before the first Heading 3 in a group (i.e. with
  no current question yet) have nowhere to attach and are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import docx

_LEADING_MARKER_RE = re.compile(r"^\s*(?:[-•*]+|[A-Za-z]{0,2}\d+[\.\)])\s*")
DEFAULT_GROUP_NAME = "Imported questions"


@dataclass
class ParsedQuestion:
    question_text: str
    explanation: str = ""  # one or more points, joined by newlines


@dataclass
class ParsedGroup:
    name: str
    questions: list[ParsedQuestion] = field(default_factory=list)


def _clean_line(text: str) -> str:
    return _LEADING_MARKER_RE.sub("", text).strip()


def parse_question_bank_docx(file_path: str) -> list[ParsedGroup]:
    document = docx.Document(file_path)
    groups: list[ParsedGroup] = []
    current_group: ParsedGroup | None = None
    current_question: ParsedQuestion | None = None
    explanation_lines: list[str] = []

    def flush_question() -> None:
        nonlocal explanation_lines
        if current_question is not None:
            current_question.explanation = "\n".join(explanation_lines).strip()
        explanation_lines = []

    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = (para.style.name if para.style else "") or ""

        if style_name == "Heading 2":
            flush_question()
            current_question = None
            current_group = ParsedGroup(name=text)
            groups.append(current_group)
            continue

        if style_name == "Heading 3":
            flush_question()
            if current_group is None:
                current_group = ParsedGroup(name=DEFAULT_GROUP_NAME)
                groups.append(current_group)
            cleaned = _clean_line(text)
            if cleaned:
                current_question = ParsedQuestion(question_text=cleaned)
                current_group.questions.append(current_question)
            else:
                current_question = None
            continue

        # A plain paragraph: a detail/point for the current question, if any.
        if current_question is not None:
            cleaned = _clean_line(text)
            if cleaned:
                explanation_lines.append(cleaned)

    flush_question()
    return [g for g in groups if g.questions]
