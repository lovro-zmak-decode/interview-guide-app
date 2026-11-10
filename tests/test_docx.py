import io

from docx import Document

from interview_app.docx_generator import build_docx, build_group_preview_docx
from interview_app.schema import CuratedQuestionGroup, InterviewQuestion
from tests.conftest import sample_summary


def read(summary, logs=None):
    buffer = io.BytesIO()
    build_docx(summary, buffer, logs=logs)
    buffer.seek(0)
    document = Document(buffer)
    text = "\n".join(p.text for p in document.paragraphs)
    table = [[cell.text for cell in row.cells] for row in document.tables[0].rows] if document.tables else []
    return text, table


def log(name, **fields):
    base = {
        "name": name,
        "answers": {},
        "custom_questions": [],
        "live_notes": "",
        "evaluation": {},
        "recommendation": "",
        "second_round": "",
        "summary": None,
    }
    return {**base, **fields}


def summary_block(text="The summary", reviewed=False, suggestions="- Ask this"):
    return {"summary": text, "second_round_suggestions": suggestions, "reviewed": reviewed}


def test_a_plain_report_has_every_section_and_no_interview_notes():
    text, table = read(sample_summary())
    for heading in (
        "Candidate profile",
        "Warm-up and experience",
        "Technical depth",
        "How they think",
        "Teamwork",
        "Quick evaluation",
    ):
        assert heading in text
    assert "Warm-up question?" in text and "Teamwork question?" in text
    assert "Notes on the answer" not in text
    assert table[1][:2] == ["Basics", "Solid fundamentals"] and table[1][2:] == ["", ""]


def test_one_interviewers_notes_are_not_labelled_with_a_name():
    text, table = read(
        sample_summary(),
        [
            log(
                "ana",
                answers={"warmup:0": "Answered well"},
                live_notes="Line one\nLine two",
                evaluation={"0": {"grade": "4", "note": "solid"}},
                recommendation="yes",
            )
        ],
    )
    assert "Notes on the answer: Answered well" in text
    assert "Interview notes" in text and "Line two" in text
    assert "Overall recommendation: yes" in text
    assert table[1][2:] == ["4/5", "solid"]
    assert "ana" not in text


def test_two_interviewers_are_labelled_by_name_everywhere():
    first = log(
        "ana",
        answers={"warmup:0": "Ana's answer"},
        live_notes="Ana live",
        recommendation="yes",
        evaluation={"0": {"grade": "4", "note": "ana note"}},
        summary=summary_block("Ana summary"),
    )
    second = log(
        "ben",
        answers={"warmup:0": "Ben's answer"},
        live_notes="Ben live",
        recommendation="no",
        evaluation={"0": {"grade": "2", "note": "ben note"}},
        summary=summary_block("Ben summary"),
    )
    text, table = read(sample_summary(), [first, second])
    assert "Notes on the answer (ana): Ana's answer" in text and "Notes on the answer (ben): Ben's answer" in text
    assert "Interview notes (ana)" in text and "Interview notes (ben)" in text
    assert "Overall recommendation (ana): yes" in text and "Overall recommendation (ben): no" in text
    assert "Sažetak razgovora (ana)" in text and "Sažetak razgovora (ben)" in text
    assert table[1][2] == "ana: 4/5\nben: 2/5"
    assert table[1][3] == "ana: ana note\nben: ben note"


def test_the_summary_block_sits_before_everything_else_and_marks_drafts():
    text, _ = read(sample_summary(), [log("ana", summary=summary_block())])
    assert text.index("Sažetak razgovora") < text.index("Candidate profile")
    assert "Sažetak razgovora (nacrt, nije pregledano)" in text
    reviewed, _ = read(sample_summary(), [log("ana", summary=summary_block(reviewed=True))])
    assert "nacrt" not in reviewed


def test_the_second_round_choice_is_shown_only_when_the_interviewer_set_it():
    unset, _ = read(sample_summary(), [log("ana", summary=summary_block())])
    assert "Preporuka za drugi krug: DA / NE" in unset
    chosen, _ = read(sample_summary(), [log("ana", summary=summary_block(), second_round="NE")])
    assert "Preporuka za drugi krug: NE" in chosen


def test_suggestions_become_bullet_points():
    text, _ = read(sample_summary(), [log("ana", summary=summary_block(suggestions="- First\n- Second"))])
    assert "Prijedlozi za dodatna pitanja na 2. krugu, napomene i sl.:" in text
    assert "First" in text and "Second" in text


def test_own_questions_come_before_the_question_bank_appendix():
    summary = sample_summary(
        curated_question_groups=[
            CuratedQuestionGroup(
                group_name="Bank", questions=[InterviewQuestion(question="Bank question?", guidance="g")]
            )
        ]
    )
    text, _ = read(summary, [log("ana", custom_questions=[{"question": "Mine?", "answer": "Fine"}])])
    assert "O1. Mine?" in text and "Notes on the answer: Fine" in text
    assert text.index("Own questions") < text.index("Additional questions from the Questions DB")
    assert "Bank question?" in text


def test_a_group_preview_can_be_built():
    class Question:
        question_text = "Preview question?"
        explanation = "Because"

    buffer = io.BytesIO()
    build_group_preview_docx("My group", [Question()], buffer)
    buffer.seek(0)
    assert "Preview question?" in "\n".join(p.text for p in Document(buffer).paragraphs)
