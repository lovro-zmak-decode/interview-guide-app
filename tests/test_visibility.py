"""Who sees whose marks: hidden only while an interview is in progress."""

import pytest

SCORING = {
    "evaluation": {"0": {"grade": "4", "note": "solid"}},
    "recommendation": "yes",
    "second_round": "DA",
}


@pytest.fixture
def pair(make_user, make_guide, login):
    owner = make_user("owner@example.com", "user")
    admin = make_user("admin@example.com", "admin")
    gid = make_guide(owner)
    return {"gid": gid, "owner": login(owner), "admin": login(admin)}


def others_of(client, gid):
    return client.get(f"/history/{gid}/others").get_json()["others"][0]["data"]


def scoring_visible(data):
    return bool(data["evaluation"] or data["recommendation"] or data["second_round"] or data["summary"])


def start(client, gid):
    return client.post(f"/history/{gid}/log", json={"started": True})


def end(client, gid):
    return client.post(f"/history/{gid}/log", json={"started": False})


def write(client, gid, text):
    client.post(f"/history/{gid}/log", json={"answers": {"warmup:0": text}, **SCORING})


def test_scoring_stays_hidden_while_either_person_is_interviewing(pair):
    gid = pair["gid"]
    for who in ("owner", "admin"):
        start(pair[who], gid)
        write(pair[who], gid, f"answer from {who}")
    for viewer, other in (("owner", "admin"), ("admin", "owner")):
        data = others_of(pair[viewer], gid)
        assert data["answers"] == {"warmup:0": f"answer from {other}"}  # answers are shared
        assert not scoring_visible(data)


def test_one_person_finishing_is_not_enough(pair):
    gid = pair["gid"]
    for who in ("owner", "admin"):
        start(pair[who], gid)
        write(pair[who], gid, "x")
    end(pair["owner"], gid)
    assert not scoring_visible(others_of(pair["owner"], gid))  # owner is done, admin still interviewing
    assert not scoring_visible(others_of(pair["admin"], gid))  # admin is still interviewing himself


def test_everything_is_visible_once_both_have_finished(pair):
    gid = pair["gid"]
    for who in ("owner", "admin"):
        start(pair[who], gid)
        write(pair[who], gid, "x")
        end(pair[who], gid)
    for viewer in ("owner", "admin"):
        data = others_of(pair[viewer], gid)
        assert data["evaluation"] == SCORING["evaluation"]
        assert (data["recommendation"], data["second_round"]) == ("yes", "DA")


def test_starting_again_hides_the_scoring_again(pair):
    gid = pair["gid"]
    for who in ("owner", "admin"):
        start(pair[who], gid)
        write(pair[who], gid, "x")
        end(pair[who], gid)
    start(pair["admin"], gid)
    assert not scoring_visible(others_of(pair["owner"], gid))
    assert not scoring_visible(others_of(pair["admin"], gid))


def test_the_page_never_contains_hidden_scoring(pair):
    gid = pair["gid"]
    for who in ("owner", "admin"):
        start(pair[who], gid)
    pair["admin"].post(
        f"/history/{gid}/log",
        json={"evaluation": {"0": {"grade": "2", "note": "SECRET_ADMIN_NOTE"}}, "recommendation": "no"},
    )
    page = pair["owner"].get(f"/history/{gid}").get_data(as_text=True)
    assert "SECRET_ADMIN_NOTE" not in page


def test_you_always_see_your_own_scoring(pair):
    gid = pair["gid"]
    start(pair["owner"], gid)
    pair["owner"].post(f"/history/{gid}/log", json={"evaluation": {"0": {"grade": "3", "note": "MY_OWN_NOTE"}}})
    assert "MY_OWN_NOTE" in pair["owner"].get(f"/history/{gid}").get_data(as_text=True)


def test_a_person_with_nothing_written_is_not_listed(pair):
    assert pair["owner"].get(f"/history/{pair['gid']}/others").get_json() == {"others": []}


def test_presence_shows_who_is_interviewing(pair):
    gid = pair["gid"]
    start(pair["admin"], gid)
    other = pair["owner"].get(f"/history/{gid}/others").get_json()["others"][0]
    assert other["name"] == "admin"
    assert other["started"] is True
