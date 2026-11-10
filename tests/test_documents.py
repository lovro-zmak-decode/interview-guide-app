"""Generating a guide, the stored CV/LinkedIn files, regenerating and deleting."""

import io

import pytest

import app as app_module
from interview_app.models import GeneratedGuide, GuideDocument, InterviewRole, StoredFile

CV = b"Jane Doe CV: python, flask, postgres"
LINKEDIN = b"Jane Doe on LinkedIn"


@pytest.fixture
def user(make_user, login):
    uid = make_user("jane@example.com", "user")
    return {"id": uid, "client": login(uid)}


@pytest.fixture
def prompt(make_prompt):
    return make_prompt("technical")


def generate(client, prompt_id, **extra):
    data = {
        "candidate_name": "Jane Doe",
        "role_title": "Backend Developer",
        "prompt_id": str(prompt_id),
        "duration_minutes": "60",
        **extra,
    }
    return client.post("/generate", data=data, content_type="multipart/form-data")


def upload(content, name):
    return (io.BytesIO(content), name)


def guides():
    with app_module.app.app_context():
        return [
            (g.id, g.research_text, [(d.kind, d.filename, d.storage_key) for d in g.documents])
            for g in GeneratedGuide.query.order_by(GeneratedGuide.id)
        ]


def test_generating_a_guide_stores_the_uploaded_files(user, prompt, llm):
    response = generate(
        user["client"], prompt, cv_file=upload(CV, "My CV.txt"), linkedin_file=upload(LINKEDIN, "li.txt")
    )
    assert response.status_code == 200
    ((gid, research, documents),) = guides()
    assert documents == [
        ("cv", "My CV.txt", f"guides/{gid}/cv.txt"),
        ("linkedin", "li.txt", f"guides/{gid}/linkedin.txt"),
    ]
    assert "Jane Doe CV" in research and "Jane Doe on LinkedIn" in research
    assert "Jane Doe CV" in llm.calls[0][0]  # the extracted text reached the model


def test_stored_files_can_be_downloaded_by_those_who_may_open_the_guide(user, prompt, llm, make_user, login):
    generate(user["client"], prompt, cv_file=upload(CV, "My CV.txt"))
    gid = guides()[0][0]
    response = user["client"].get(f"/history/{gid}/files/cv")
    assert response.status_code == 200
    assert response.data == CV
    assert response.mimetype == "text/plain"
    assert "My CV.txt" in response.headers["Content-Disposition"]
    assert user["client"].get(f"/history/{gid}/files/linkedin").status_code == 302  # none was uploaded
    assert login(make_user("other@example.com")).get(f"/history/{gid}/files/cv").status_code == 302
    page = user["client"].get(f"/history/{gid}").get_data(as_text=True)
    assert f"/history/{gid}/files/cv" in page and "My CV.txt" in page


def test_a_cv_is_required(user, prompt, llm):
    response = generate(user["client"], prompt)
    assert response.status_code == 302
    assert guides() == []


def test_unsupported_cv_formats_are_refused(user, prompt, llm):
    assert generate(user["client"], prompt, cv_file=upload(b"MZ", "virus.exe")).status_code == 302
    assert guides() == []
    assert llm.calls == []


def test_the_role_typed_on_the_form_is_remembered(user, prompt, llm):
    generate(user["client"], prompt, cv_file=upload(CV, "cv.txt"))
    with app_module.app.app_context():
        assert [r.name for r in InterviewRole.query.all()] == ["Backend Developer"]


def test_additional_notes_reach_the_prompt(user, prompt, llm):
    generate(user["client"], prompt, cv_file=upload(CV, "cv.txt"), additional_notes="Focus on Kafka")
    assert "Focus on Kafka" in llm.calls[0][0]


def test_regenerating_without_a_new_cv_reuses_and_copies_the_stored_files(user, prompt, llm):
    generate(user["client"], prompt, cv_file=upload(CV, "My CV.txt"), linkedin_file=upload(LINKEDIN, "li.txt"))
    first = guides()[0][0]
    response = generate(user["client"], prompt, clone_from=str(first), duration_minutes="45")
    assert response.status_code == 200
    (_, _, first_docs), (second, research, second_docs) = guides()
    assert "Jane Doe CV" in llm.calls[1][0]  # the stored text was used, no upload needed
    assert [(k, name) for k, name, _ in second_docs] == [(k, name) for k, name, _ in first_docs]
    assert all(key.startswith(f"guides/{second}/") for _, _, key in second_docs)  # its own copies
    assert user["client"].get(f"/history/{second}/files/cv").data == CV


def test_regenerating_with_a_new_cv_stores_only_the_new_file(user, prompt, llm):
    generate(user["client"], prompt, cv_file=upload(CV, "old.txt"), linkedin_file=upload(LINKEDIN, "li.txt"))
    first = guides()[0][0]
    generate(user["client"], prompt, clone_from=str(first), cv_file=upload(b"New CV text", "new.txt"))
    second_docs = guides()[1][2]
    assert [(kind, name) for kind, name, _ in second_docs] == [("cv", "new.txt")]
    assert "New CV text" in llm.calls[1][0]


def test_the_regenerate_form_is_prefilled_and_lists_the_stored_files(user, prompt, llm):
    generate(user["client"], prompt, cv_file=upload(CV, "My CV.txt"), duration_minutes="45")
    gid = guides()[0][0]
    page = user["client"].get(f"/history/{gid}/clone").get_data(as_text=True)
    assert 'value="Jane Doe"' in page and 'value="Backend Developer"' in page
    assert "Stored with the guide" in page and "My CV.txt" in page


def test_deleting_a_guide_removes_its_files_and_only_its_files(user, prompt, llm):
    generate(user["client"], prompt, cv_file=upload(CV, "a.txt"))
    generate(user["client"], prompt, cv_file=upload(b"Other CV", "b.txt"))
    first, second = guides()[0][0], guides()[1][0]
    user["client"].post(f"/history/{first}/delete")
    with app_module.app.app_context():
        assert [g.id for g in GeneratedGuide.query.all()] == [second]
        assert [d.guide_id for d in GuideDocument.query.all()] == [second]
        assert [f.key for f in StoredFile.query.all()] == [f"guides/{second}/cv.txt"]


def test_the_word_report_is_built_from_the_database(user, prompt, llm):
    generate(user["client"], prompt, cv_file=upload(CV, "cv.txt"))
    with app_module.app.app_context():
        filename = GeneratedGuide.query.one().docx_filename
    response = user["client"].get(f"/download/{filename}")
    assert response.status_code == 200
    assert response.data[:2] == b"PK"
