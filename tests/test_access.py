import pytest

import app as app_module
from interview_app.models import GeneratedGuide


@pytest.fixture
def people(make_user, make_guide):
    owner = make_user("owner@example.com", "user")
    admin = make_user("admin@example.com", "admin")
    outsider = make_user("outsider@example.com", "user")
    return {"owner": owner, "admin": admin, "outsider": outsider, "guide": make_guide(owner)}


def test_owner_and_admins_can_open_a_guide_but_other_users_cannot(people, login):
    gid = people["guide"]
    assert login(people["owner"]).get(f"/history/{gid}").status_code == 200
    assert login(people["admin"]).get(f"/history/{gid}").status_code == 200
    response = login(people["outsider"]).get(f"/history/{gid}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/history")


def test_the_guide_list_only_shows_your_own_guides(people, login, make_guide):
    make_guide(people["outsider"], docx_filename="interview_guide_other.docx", summary=None)
    page = login(people["outsider"]).get("/history").get_data(as_text=True)
    assert page.count("/history/") >= 1
    assert f'/history/{people["guide"]}"' not in page


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/history/{gid}/log", {"live_notes": "x"}),
        ("post", "/history/{gid}/summary", {}),
        ("get", "/history/{gid}/others", None),
    ],
)
def test_interview_endpoints_reject_outsiders(people, login, method, path, payload):
    client = login(people["outsider"])
    url = path.format(gid=people["guide"])
    response = client.post(url, json=payload) if method == "post" else client.get(url)
    assert response.status_code == 403


def test_interview_endpoints_need_a_login(people):
    client = app_module.app.test_client()
    assert client.post(f"/history/{people['guide']}/log", json={}).status_code == 302
    assert client.get(f"/history/{people['guide']}/others").status_code == 302


def test_unknown_guides_are_reported_as_missing(people, login):
    client = login(people["owner"])
    assert client.post("/history/9999/log", json={}).status_code == 404
    assert client.get("/history/9999/others").status_code == 404


def test_source_files_and_clone_form_follow_the_same_access_rules(people, login):
    gid = people["guide"]
    assert login(people["outsider"]).get(f"/history/{gid}/files/cv").status_code == 302
    assert login(people["outsider"]).get(f"/history/{gid}/clone").status_code == 302
    assert login(people["admin"]).get(f"/history/{gid}/clone").status_code == 200


def test_word_download_is_limited_to_owner_and_admins(people, login):
    filename = f"interview_guide_{people['owner']:08x}.docx"
    for who in ("owner", "admin"):
        response = login(people[who]).get(f"/download/{filename}")
        assert response.status_code == 200
        assert "wordprocessingml" in response.mimetype
        assert response.data[:2] == b"PK"
    assert login(people["outsider"]).get(f"/download/{filename}").status_code == 302
    assert login(people["owner"]).get("/download/nothing.docx").status_code == 302


def test_deleting_is_limited_to_owner_and_admins(people, login):
    gid = people["guide"]
    login(people["outsider"]).post(f"/history/{gid}/delete")
    with app_module.app.app_context():
        assert GeneratedGuide.query.count() == 1
    login(people["owner"]).post(f"/history/{gid}/delete")
    with app_module.app.app_context():
        assert GeneratedGuide.query.count() == 0


def test_only_admins_can_manage_prompts_and_see_all_guides(people, login):
    assert login(people["owner"]).get("/system-prompts/").status_code != 200
    assert login(people["admin"]).get("/system-prompts/").status_code == 200
    assert login(people["owner"]).get("/guides/all").status_code != 200
    assert login(people["admin"]).get("/guides/all").status_code == 200
