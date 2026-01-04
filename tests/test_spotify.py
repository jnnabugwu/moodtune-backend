import httpx
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core import config as config_module
from app.services import spotify_api, spotify_auth


def test_generate_authorize_url_uses_settings(monkeypatch):
    monkeypatch.setattr(config_module.settings, "SPOTIFY_CLIENT_ID", "client123")
    monkeypatch.setattr(config_module.settings, "SPOTIFY_CLIENT_SECRET", "secret456")
    monkeypatch.setattr(
        config_module.settings,
        "SPOTIFY_REDIRECT_URI",
        "http://localhost:8000/api/v1/spotify/callback",
    )
    monkeypatch.setattr(config_module.settings, "SPOTIFY_SCOPES", "user-read-email")

    url = spotify_auth.generate_authorize_url("state123")

    assert "client_id=client123" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fspotify%2Fcallback" in url
    assert "scope=user-read-email" in url
    assert "state=state123" in url


@pytest.mark.asyncio
async def test_get_valid_spotify_token_refreshes_expired(monkeypatch):
    user_id = uuid4()
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    # Fake Supabase client/response chain
    class FakeResp:
        def __init__(self, data=None, error=None):
            self.data = data
            self.error = error

    class FakeTable:
        def __init__(self, records):
            self.records = records
            self._updates = None
            self._user = None

        def select(self, *args, **kwargs):
            return self

        def eq(self, field, value):
            self._user = value
            return self

        def maybe_single(self):
            return self

        def update(self, updates):
            self._updates = updates
            return self

        def execute(self):
            if self._updates is not None:
                rec = self.records[0]
                rec.update(self._updates)
                return FakeResp([rec])
            rec = next(
                (r for r in self.records if str(r["user_id"]) == self._user), None
            )
            return FakeResp(rec)

    class FakeSupabase:
        def __init__(self, records):
            self.records = records

        def table(self, name):
            return FakeTable(self.records)

    records = [
        {
            "id": "conn1",
            "user_id": str(user_id),
            "spotify_user_id": "spotify_user",
            "access_token": "old_token",
            "refresh_token": "refresh_token",
            "expires_at": expired_at.isoformat(),
            "updated_at": None,
        }
    ]

    async def fake_refresh(token: str):
        return {
            "access_token": "new_token",
            "expires_in": 3600,
            "refresh_token": "new_refresh",
        }

    monkeypatch.setattr(spotify_api, "_supabase", FakeSupabase(records))
    monkeypatch.setattr(spotify_api, "refresh_access_token", fake_refresh)

    token = await spotify_api.get_valid_spotify_token(user_id)

    updated = records[0]
    assert token == "new_token"
    assert updated["access_token"] == "new_token"
    assert updated["refresh_token"] == "new_refresh"
    assert datetime.fromisoformat(updated["expires_at"]) > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_user_profile(monkeypatch):
    profile_payload = {
        "id": "spotify_user",
        "display_name": "Test User",
        "email": "user@example.com",
        "images": [{"url": "https://img.test/avatar.jpg"}],
        "followers": {"total": 42},
        "product": "premium",
    }

    class FakeResponse:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "error", request=None, response=None
                )

        def json(self):
            return self._data

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse(profile_payload)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    profile = await spotify_api.get_user_profile("token123")
    assert profile["id"] == "spotify_user"
    assert profile["display_name"] == "Test User"
    assert profile["followers"]["total"] == 42

