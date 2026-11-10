"""Google sign-in, end to end, against a fake Google.

Authlib talks to Google over `requests`. These tests answer those HTTP calls themselves (the
OpenID metadata, the signing keys and the token endpoint) and sign a real RS256 ID token with a
throwaway key, so the whole flow runs: the redirect, the state and nonce checks, the token
exchange and the ID token validation. No network, no credentials.
"""

import base64
import json
import os
import time
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import app as app_module
from interview_app.models import User

CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]  # set in conftest before the app is created
ISSUER = "https://accounts.google.com"
KEY_ID = "test-key"
# Authlib caches the signing keys on the shared client, and Google's real keys persist, so the
# fake publishes one fixed key for the whole run.
PUBLISHED_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

METADATA = {
    "issuer": ISSUER,
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
    "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
    "id_token_signing_alg_values_supported": ["RS256"],
    "response_types_supported": ["code"],
    "subject_types_supported": ["public"],
    "scopes_supported": ["openid", "email", "profile"],
    "code_challenge_methods_supported": ["S256"],
}


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def int_to_b64url(number: int) -> str:
    return b64url(number.to_bytes((number.bit_length() + 7) // 8, "big"))


class FakeGoogle:
    """Answers authlib's HTTP calls and signs ID tokens."""

    def __init__(self) -> None:
        self.key = PUBLISHED_KEY  # the key tokens are signed with
        self.claims_for_next_token: dict = {}
        self.token_status = 200

    def jwks(self) -> dict:
        numbers = PUBLISHED_KEY.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": KEY_ID,
                    "use": "sig",
                    "alg": "RS256",
                    "n": int_to_b64url(numbers.n),
                    "e": int_to_b64url(numbers.e),
                }
            ]
        }

    def id_token(self, nonce: str, **claims) -> str:
        now = int(time.time())
        payload = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "1234567890",
            "iat": now,
            "exp": now + 3600,
            "nonce": nonce,
            "email": "jane@example.com",
            "email_verified": True,
            "name": "Jane Doe",
            **claims,
        }
        header = {"alg": "RS256", "typ": "JWT", "kid": KEY_ID}
        signing_input = f"{b64url(json.dumps(header).encode())}.{b64url(json.dumps(payload).encode())}"
        signature = self.key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        return f"{signing_input}.{b64url(signature)}"

    def respond(self, method: str, url: str) -> requests.Response:
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        if url == "https://accounts.google.com/.well-known/openid-configuration":
            body = METADATA
        elif url == METADATA["jwks_uri"]:
            body = self.jwks()
        elif url == METADATA["token_endpoint"]:
            response.status_code = self.token_status
            body = self.claims_for_next_token or {"error": "invalid_grant"}
        else:
            raise AssertionError(f"unexpected HTTP call: {method} {url}")
        response._content = json.dumps(body).encode()
        return response


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(requests.Session, "request", lambda self, method, url, *args, **kw: fake.respond(method, url))
    return fake


def start_login(client):
    """Begin the sign-in and return the state and nonce Authlib sent to Google."""
    response = client.get("/auth/google/login")
    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == METADATA["authorization_endpoint"]
    query = parse_qs(location.query)
    assert query["client_id"] == [CLIENT_ID]
    assert "openid" in query["scope"][0]
    return query["state"][0], query["nonce"][0]


def finish_login(client, google, state, nonce, **claims):
    google.claims_for_next_token = {
        "access_token": "access-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "id_token": google.id_token(nonce, **claims),
    }
    return client.get(f"/auth/google/callback?code=auth-code&state={state}")


def users():
    with app_module.app.app_context():
        return [(u.email, u.role) for u in User.query.order_by(User.id)]


def test_the_login_page_always_shows_the_google_button(make_user):
    make_user("boss@example.com", "superadmin")
    page = app_module.app.test_client().get("/login").get_data(as_text=True)
    assert "/auth/google/login" in page


def test_without_credentials_google_sign_in_explains_itself(monkeypatch, make_user):
    make_user("boss@example.com", "superadmin")
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    response = app_module.app.test_client().get("/auth/google/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_a_new_google_user_gets_an_account_and_is_signed_in(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    state, nonce = start_login(client)
    response = finish_login(client, google, state, nonce)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert ("jane@example.com", "user") in users()
    assert client.get("/history").status_code == 200  # signed in


def test_the_email_is_lowercased_and_matches_an_existing_account(google, make_user):
    """Signing in with Google reuses the account with the same email instead of creating a second one."""
    existing = make_user("jane@example.com", "admin")
    client = app_module.app.test_client()
    state, nonce = start_login(client)
    finish_login(client, google, state, nonce, email="Jane@Example.com")
    assert users() == [("jane@example.com", "admin")]
    with client.session_transaction() as session:
        assert session["_user_id"] == str(existing)


def test_a_wrong_state_is_rejected(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    _, nonce = start_login(client)
    response = finish_login(client, google, "not-the-state-we-sent", nonce)
    assert response.headers["Location"].endswith("/login")
    assert users() == [("boss@example.com", "superadmin")]


def test_a_token_for_another_application_is_rejected(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    state, nonce = start_login(client)
    response = finish_login(client, google, state, nonce, aud="someone-elses-client-id")
    assert response.headers["Location"].endswith("/login")
    assert users() == [("boss@example.com", "superadmin")]


def test_a_token_with_the_wrong_nonce_is_rejected(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    state, _ = start_login(client)
    response = finish_login(client, google, state, "a-different-nonce")
    assert response.headers["Location"].endswith("/login")
    assert users() == [("boss@example.com", "superadmin")]


def test_an_expired_token_is_rejected(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    state, nonce = start_login(client)
    response = finish_login(client, google, state, nonce, exp=int(time.time()) - 3600)
    assert response.headers["Location"].endswith("/login")
    assert users() == [("boss@example.com", "superadmin")]


def test_a_token_signed_with_an_unknown_key_is_rejected(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    state, nonce = start_login(client)
    google.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # a key Google never published
    response = finish_login(client, google, state, nonce)
    assert response.headers["Location"].endswith("/login")
    assert users() == [("boss@example.com", "superadmin")]


def test_a_failed_token_exchange_is_reported_not_raised(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    state, _ = start_login(client)
    google.token_status = 400
    response = client.get(f"/auth/google/callback?code=auth-code&state={state}")
    assert response.headers["Location"].endswith("/login")
    assert users() == [("boss@example.com", "superadmin")]


def test_a_token_without_an_email_is_rejected(google, make_user):
    make_user("boss@example.com", "superadmin")
    client = app_module.app.test_client()
    state, nonce = start_login(client)
    response = finish_login(client, google, state, nonce, email="")
    assert response.headers["Location"].endswith("/login")
    assert users() == [("boss@example.com", "superadmin")]
