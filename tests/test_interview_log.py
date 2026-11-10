import pytest

from interview_app import interview_log as ilog
from tests.conftest import sample_summary


@pytest.fixture
def summary():
    return sample_summary()


def merged(summary, payload, data=None):
    return ilog.merge_update(data or ilog.empty_data(), payload, summary)


def test_answers_are_stored_trimmed_and_blank_ones_removed(summary):
    data = merged(summary, {"answers": {"warmup:0": "  good answer  ", "quick:0": "x"}})
    assert data["answers"] == {"warmup:0": "good answer", "quick:0": "x"}
    data = merged(summary, {"answers": {"quick:0": "   "}}, data)
    assert data["answers"] == {"warmup:0": "good answer"}


@pytest.mark.parametrize("key", ["nope:0", "warmup:5", "warmup", "teamwork:-1"])
def test_unknown_question_keys_are_rejected(summary, key):
    with pytest.raises(ValueError):
        merged(summary, {"answers": {key: "text"}})


def test_evaluation_accepts_grades_one_to_five_only(summary):
    data = merged(summary, {"evaluation": {"0": {"grade": "4", "note": "ok"}, "1": {"grade": ""}}})
    assert data["evaluation"]["0"] == {"grade": "4", "note": "ok"}
    for bad in ("0", "6", "four"):
        with pytest.raises(ValueError):
            merged(summary, {"evaluation": {"0": {"grade": bad}}})


def test_evaluation_rows_must_exist(summary):
    with pytest.raises(ValueError):
        merged(summary, {"evaluation": {"9": {"grade": "3"}}})


def test_recommendation_must_be_one_of_the_options(summary):
    assert ilog.recommendation_options(summary) == ["definitely yes", "yes", "no", "definitely not"]
    assert merged(summary, {"recommendation": "yes"})["recommendation"] == "yes"
    with pytest.raises(ValueError):
        merged(summary, {"recommendation": "maybe"})


def test_second_round_is_only_da_ne_or_empty(summary):
    assert merged(summary, {"second_round": "DA"})["second_round"] == "DA"
    assert merged(summary, {"second_round": ""})["second_round"] == ""
    with pytest.raises(ValueError):
        merged(summary, {"second_round": "MAYBE"})


def test_custom_questions_keep_order_and_drop_blank_entries(summary):
    data = merged(
        summary,
        {
            "custom_questions": [
                {"question": " First? ", "answer": " Yes "},
                {"question": "", "answer": ""},
                {"question": "Second?", "answer": ""},
            ]
        },
    )
    assert data["custom_questions"] == [
        {"question": "First?", "answer": "Yes"},
        {"question": "Second?", "answer": ""},
    ]


@pytest.mark.parametrize(
    "bad",
    ["text", [1], [{"question": 5}], [{"question": "q"}] * (ilog.MAX_CUSTOM_QUESTIONS + 1)],
)
def test_invalid_custom_questions_are_rejected(summary, bad):
    with pytest.raises(ValueError):
        merged(summary, {"custom_questions": bad})


def test_text_fields_have_a_size_limit(summary):
    with pytest.raises(ValueError):
        merged(summary, {"live_notes": "x" * (ilog.MAX_FIELD_CHARS + 1)})


def test_summary_can_only_be_edited_once_it_exists(summary):
    with pytest.raises(ValueError):
        merged(summary, {"summary_edit": {"reviewed": True}})
    data = ilog.empty_data()
    ilog.store_summary(data, "Text", "Suggestions")
    assert data["summary"]["reviewed"] is False
    data = merged(summary, {"summary_edit": {"summary": "Edited", "reviewed": True}}, data)
    assert (data["summary"]["summary"], data["summary"]["reviewed"]) == ("Edited", True)


def test_only_answers_own_questions_and_live_notes_are_shareable(summary):
    data = merged(
        summary,
        {
            "answers": {"warmup:0": "a"},
            "custom_questions": [{"question": "q", "answer": "a"}],
            "live_notes": "notes",
            "evaluation": {"0": {"grade": "5"}},
            "recommendation": "yes",
            "second_round": "DA",
        },
    )
    ilog.store_summary(data, "S", "T")
    shared = ilog.shareable(data)
    assert shared["answers"] == {"warmup:0": "a"}
    assert shared["custom_questions"] == [{"question": "q", "answer": "a"}]
    assert shared["live_notes"] == "notes"
    assert shared["evaluation"] == {}
    assert (shared["recommendation"], shared["second_round"], shared["summary"]) == ("", "", None)


def test_has_content_ignores_an_empty_log(summary):
    assert not ilog.has_content(ilog.empty_data())
    assert ilog.has_content(merged(summary, {"live_notes": "x"}))
    assert ilog.has_content(merged(summary, {"custom_questions": [{"question": "q", "answer": ""}]}))


def test_parse_data_survives_broken_json():
    assert ilog.parse_data("not json") == ilog.empty_data()
    assert ilog.parse_data(None) == ilog.empty_data()


def test_text_for_the_summary_prompt_includes_notes_grades_and_own_questions(summary):
    data = merged(
        summary,
        {
            "answers": {"warmup:0": "Answered well"},
            "custom_questions": [{"question": "My own question?", "answer": "Fine"}],
            "evaluation": {"0": {"grade": "4", "note": "solid"}},
        },
    )
    text = ilog.questions_and_answers_text(summary, data["answers"], data["custom_questions"])
    assert "Warm-up question?" in text and "Answered well" in text
    assert "(no notes)" in text  # the other questions have none
    assert "added themselves" in text and "My own question?" in text and "Fine" in text
    evaluation = ilog.evaluation_text(summary, data["evaluation"])
    assert "Basics: 4/5 (solid)" in evaluation and "Communication: not graded" in evaluation
