from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gotrue.errors import AuthApiError

from app.api import deps
from app.api.v1 import account
from app.crud import spotify as crud_spotify
from app.services import account_service

EMAIL = "someone@example.com"
TOKEN = "secret-access-token"
USER = {"id": str(uuid4()), "email": EMAIL, "user_metadata": {}}


class _FakeAdmin:
    def __init__(self, calls):
        self.calls = calls

    def delete_user(self, user_id):
        self.calls["order"].append(("delete_user", user_id))
        error = self.calls.get("delete_user_error")
        if error is not None:
            raise error


class _FakeAuth:
    def __init__(self, calls):
        self.admin = _FakeAdmin(calls)


class _FakeServiceClient:
    def __init__(self, calls):
        self.auth = _FakeAuth(calls)


@pytest.fixture
def calls():
    return {"order": [], "sentry": []}


@pytest.fixture
def app(monkeypatch, calls):
    async def fake_delete_spotify(user_id):
        calls["order"].append(("spotify", str(user_id)))
        error = calls.get("spotify_error")
        if error is not None:
            raise error
        return True

    monkeypatch.setattr(
        crud_spotify, "delete_spotify_connection_by_user", fake_delete_spotify
    )
    monkeypatch.setattr(
        account_service,
        "get_supabase_service_client",
        lambda: _FakeServiceClient(calls),
    )
    monkeypatch.setattr(
        account.sentry_sdk, "capture_exception", lambda e: calls["sentry"].append(e)
    )

    app = FastAPI()
    app.include_router(account.router, prefix="/api/v1/account")
    app.dependency_overrides[deps.get_current_user] = lambda: USER
    return app


def _delete(app):
    return TestClient(app).delete(
        "/api/v1/account", headers={"Authorization": f"Bearer {TOKEN}"}
    )


def test_router_is_mounted_at_account():
    from app.api.v1.api import api_router

    routes = {(r.path, tuple(sorted(r.methods))) for r in api_router.routes}
    assert ("/account", ("DELETE",)) in routes


# AC1
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc"}])
def test_missing_token_is_401(app, calls, headers):
    app.dependency_overrides.pop(deps.get_current_user)

    resp = TestClient(app).delete("/api/v1/account", headers=headers)

    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert calls["order"] == []


# AC1, on the real app so the mounted path and auth wiring are exercised.
def test_missing_token_is_401_on_mounted_app(calls):
    from app.main import app as real_app

    resp = TestClient(real_app).delete("/api/v1/account")

    assert resp.status_code == 401
    assert calls["order"] == []


def test_invalid_token_is_401(app, calls, monkeypatch):
    app.dependency_overrides.pop(deps.get_current_user)

    class _RejectingClient:
        class auth:
            @staticmethod
            def get_user(token):
                raise ValueError("invalid JWT")

    monkeypatch.setattr(deps, "get_supabase_client", lambda: _RejectingClient())

    resp = _delete(app)

    assert resp.status_code == 401
    assert calls["order"] == []


# AC2
def test_deletes_spotify_then_auth_user(app, calls):
    resp = _delete(app)

    assert resp.status_code == 204
    assert resp.content == b""
    assert calls["order"] == [
        ("spotify", USER["id"]),
        ("delete_user", USER["id"]),
    ]
    assert calls["sentry"] == []


# AC3
def test_already_deleted_user_is_204(app, calls):
    calls["delete_user_error"] = AuthApiError("User not found", 404)

    resp = _delete(app)

    assert resp.status_code == 204
    assert calls["sentry"] == []


def _assert_generic_500(resp, calls, step):
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Could not delete account"}
    assert EMAIL not in resp.text
    assert TOKEN not in resp.text
    assert len(calls["sentry"]) == 1
    reported = calls["sentry"][0]
    assert reported.step == step
    assert EMAIL not in str(reported)
    assert TOKEN not in str(reported)


# AC4
def test_spotify_failure_is_500_and_keeps_auth_user(app, calls, caplog):
    calls["spotify_error"] = RuntimeError("db down")

    resp = _delete(app)

    _assert_generic_500(resp, calls, "spotify_connection")
    assert ("delete_user", USER["id"]) not in calls["order"]
    assert EMAIL not in caplog.text
    assert TOKEN not in caplog.text


# AC4
@pytest.mark.parametrize(
    "error",
    [
        AuthApiError("Database error deleting user", 500),
        RuntimeError("timeout"),
        # Only a structured 404 means "already gone", not matching text.
        RuntimeError("upstream said: user not found"),
    ],
)
def test_delete_user_failure_is_500(app, calls, caplog, error):
    calls["delete_user_error"] = error

    resp = _delete(app)

    _assert_generic_500(resp, calls, "auth_user")
    assert calls["sentry"][0].__cause__ is error
    assert "auth_user" in caplog.text
    assert EMAIL not in caplog.text
    assert TOKEN not in caplog.text
