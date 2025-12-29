import httpx
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core import config as config_module
from app.core.database import Base
from app.models.spotify_connection import SpotifyConnection
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
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestingSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        expired_connection = SpotifyConnection(
            user_id=uuid4(),
            spotify_user_id="spotify_user",
            access_token="old_token",
            refresh_token="refresh_token",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        session.add(expired_connection)
        await session.commit()
        await session.refresh(expired_connection)

        async def fake_refresh(token: str):
            return {
                "access_token": "new_token",
                "expires_in": 3600,
                "refresh_token": "new_refresh",
            }

        monkeypatch.setattr(spotify_api, "refresh_access_token", fake_refresh)

        token = await spotify_api.get_valid_spotify_token(
            expired_connection.user_id, session
        )

        await session.refresh(expired_connection)
        assert token == "new_token"
        assert expired_connection.access_token == "new_token"
        assert expired_connection.refresh_token == "new_refresh"
        assert expired_connection.expires_at > datetime.now(timezone.utc)


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

