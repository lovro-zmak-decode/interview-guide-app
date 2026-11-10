import app as app_module
from interview_app.models import InterviewLog
from tests.conftest import DEBRIEF_SUMMARY


def post_log(client, gid, payload):
    return client.post(f"/history/{gid}/log", json=payload)


def stored(owner_id, gid):
    with app_module.app.app_context():
        return InterviewLog.query.filter_by(guide_id=gid, user_id=owner_id).one()


def test_notes_are_saved_and_shown_again(make_user, make_guide, login):
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    client = login(owner)
    post_log(client, gid, {"started": True})
    assert (
        post_log(client, gid, {"answers": {"warmup:0": "A remembered answer"}, "live_notes": "Live!"}).status_code
        == 200
    )
    page = client.get(f"/history/{gid}").get_data(as_text=True)
    assert "A remembered answer" in page and "Live!" in page
    assert 'id="end-interview"' in page  # still in interview mode after a reload


def test_normal_mode_is_read_only(make_user, make_guide, login):
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    client = login(owner)
    post_log(client, gid, {"answers": {"warmup:0": "Saved earlier"}})
    page = client.get(f"/history/{gid}").get_data(as_text=True)
    assert "Saved earlier" in page
    assert "<textarea data-answer" not in page
    assert 'id="start-interview"' in page


def test_invalid_saves_are_rejected_and_change_nothing(make_user, make_guide, login):
    from interview_app import interview_log as ilog

    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    client = login(owner)
    assert post_log(client, gid, {"answers": {"bogus:1": "x"}}).status_code == 400
    assert post_log(client, gid, {"evaluation": {"0": {"grade": "9"}}}).status_code == 400
    assert client.post(f"/history/{gid}/log", data="not json", content_type="text/plain").status_code == 400
    with app_module.app.app_context():
        logs = InterviewLog.query.filter_by(guide_id=gid).all()
        assert all(ilog.parse_data(log.data_json) == ilog.empty_data() for log in logs)


def test_oversized_saves_are_refused(make_user, make_guide, login):
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    huge = {"live_notes": "x" * 300_000}
    assert post_log(login(owner), gid, huge).status_code == 413


def test_own_questions_are_saved_in_order_without_blank_entries(make_user, make_guide, login):
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    client = login(owner)
    post_log(client, gid, {"started": True})
    post_log(
        client,
        gid,
        {
            "custom_questions": [
                {"question": "One?", "answer": "a"},
                {"question": "", "answer": ""},
                {"question": "Two?", "answer": ""},
            ]
        },
    )
    page = client.get(f"/history/{gid}").get_data(as_text=True)
    assert page.index("One?") < page.index("Two?")
    assert page.count("data-own-q>") == 3  # two saved questions plus the template for adding more


def test_the_summary_is_written_from_your_own_notes_only(make_user, make_guide, make_prompt, login, llm):
    make_prompt("summary")
    owner = make_user("owner@example.com")
    admin = make_user("admin@example.com", "admin")
    gid = make_guide(owner)
    mine, theirs = login(owner), login(admin)
    post_log(
        mine,
        gid,
        {
            "answers": {"warmup:0": "MY_ANSWER"},
            "custom_questions": [{"question": "MY_QUESTION?", "answer": "MY_NOTES"}],
            "live_notes": "MY_LIVE",
        },
    )
    post_log(theirs, gid, {"answers": {"warmup:0": "THEIR_ANSWER"}, "live_notes": "THEIR_LIVE"})
    assert mine.post(f"/history/{gid}/summary").status_code == 200
    prompt = llm.calls[-1][0]
    for text in ("MY_ANSWER", "MY_QUESTION?", "MY_NOTES", "MY_LIVE"):
        assert text in prompt
    assert "THEIR_ANSWER" not in prompt and "THEIR_LIVE" not in prompt


def test_the_summary_is_a_draft_without_a_second_round_verdict(make_user, make_guide, make_prompt, login, llm):
    make_prompt("summary")
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    client = login(owner)
    client.post(f"/history/{gid}/summary")
    from interview_app import interview_log as ilog

    data = ilog.parse_data(stored(owner, gid).data_json)
    assert data["summary"]["summary"] == DEBRIEF_SUMMARY
    assert (
        data["summary"]["second_round_suggestions"] == "- Ask A\n- Ask B"
    )  # a list from the model becomes bullet points
    assert data["summary"]["reviewed"] is False
    assert data["second_round"] == ""  # never proposed by the model


def test_the_summary_can_be_edited_marked_reviewed_and_regenerated(make_user, make_guide, make_prompt, login, llm):
    from interview_app import interview_log as ilog

    make_prompt("summary")
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    client = login(owner)
    client.post(f"/history/{gid}/summary")
    post_log(client, gid, {"summary_edit": {"summary": "Edited by me", "reviewed": True}})
    data = ilog.parse_data(stored(owner, gid).data_json)
    assert (data["summary"]["summary"], data["summary"]["reviewed"]) == ("Edited by me", True)
    client.post(f"/history/{gid}/summary")
    data = ilog.parse_data(stored(owner, gid).data_json)
    assert (data["summary"]["summary"], data["summary"]["reviewed"]) == (DEBRIEF_SUMMARY, False)


def test_writing_a_summary_without_a_summary_prompt_explains_what_to_do(make_user, make_guide, login, llm):
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    response = login(owner).post(f"/history/{gid}/summary")
    assert response.status_code == 502
    assert "summary" in response.get_json()["error"].lower()


def test_a_failing_model_call_is_reported_not_raised(make_user, make_guide, make_prompt, login, monkeypatch):
    make_prompt("summary")

    class Broken:
        name = "openai"

        def generate(self, system_prompt, user_prompt):
            raise ConnectionError("model unreachable")

    monkeypatch.setattr(app_module, "get_provider", lambda name=None: Broken())
    owner = make_user("owner@example.com")
    gid = make_guide(owner)
    response = login(owner).post(f"/history/{gid}/summary")
    assert response.status_code == 502
    assert "model unreachable" in response.get_json()["error"]
