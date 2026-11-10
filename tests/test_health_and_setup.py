import app as app_module


def test_healthz_needs_no_login_and_no_users():
    response = app_module.app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"


def test_healthz_reports_a_database_failure(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("database is down")

    monkeypatch.setattr(app_module.db.session, "execute", broken)
    assert app_module.app.test_client().get("/healthz").status_code == 503


def test_an_empty_database_sends_everyone_to_setup():
    response = app_module.app.test_client().get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/setup")


def test_the_first_account_gets_full_access():
    client = app_module.app.test_client()
    response = client.post("/setup", data={"email": "Boss@Example.com", "password": "long-enough-password"})
    assert response.status_code == 302
    with app_module.app.app_context():
        users = app_module.User.query.all()
    assert [(u.email, u.role) for u in users] == [("boss@example.com", "superadmin")]


def test_setup_rejects_a_short_password():
    client = app_module.app.test_client()
    client.post("/setup", data={"email": "boss@example.com", "password": "short"})
    with app_module.app.app_context():
        assert app_module.User.query.count() == 0


def test_setup_is_closed_once_an_account_exists(make_user):
    make_user("boss@example.com", "superadmin")
    response = app_module.app.test_client().get("/setup")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_pages_need_a_login(make_user):
    make_user("boss@example.com", "superadmin")
    response = app_module.app.test_client().get("/history")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
