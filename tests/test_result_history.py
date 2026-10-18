from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import deps
from app.api.v1 import catalog, song_analysis
from app.crud import mood_observation as crud_mood_observation
from app.crud import song_analysis as crud_song_analysis
from app.schemas.result_history import ResultHistoryCreate
from app.services.audio_analysis_service import audio_analysis_service

USER = {"id": str(uuid4()), "email": "a@b.c"}


def _body(**overrides) -> dict:
    body = {
        "source": "upload",
        "title": "Inside Outside",
        "artist": None,
        "displayed_mood": "calm",
        "displayed_source": "on_device",
        "backend_mood": "happy",
        "on_device_mood": "calm",
        "confidence": None,
        "observation_id": str(uuid4()),
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_schema_maps_to_mood_results_with_both_engines():
    body = _body()
    results = ResultHistoryCreate(**body).to_mood_results()

    assert results == {
        "primary_mood": "calm",
        "confidence": None,
        "source": "upload",
        "displayed_source": "on_device",
        "backend_mood": "happy",
        "on_device_mood": "calm",
        "observation_id": body["observation_id"],
        "title_from_filename": False,
    }


def test_schema_stores_title_from_filename():
    body = ResultHistoryCreate(**_body(title="Summer Vibes", title_from_filename=True))
    assert body.to_mood_results()["title_from_filename"] is True


def test_schema_defaults_title_from_filename_for_older_apps():
    body = _body()
    body.pop("title_from_filename", None)
    assert ResultHistoryCreate(**body).to_mood_results()["title_from_filename"] is False


def test_schema_accepts_backend_only_result():
    body = ResultHistoryCreate(
        **_body(
            displayed_source="backend",
            displayed_mood="happy",
            on_device_mood=None,
            confidence=0.81,
            observation_id=None,
        )
    )
    assert body.to_mood_results()["observation_id"] is None


def test_schema_trims_title():
    assert ResultHistoryCreate(**_body(title="  Song  ")).title == "Song"


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},
        {"title": "x" * 201},
        {"source": "spotify"},
        {"backend_mood": "serene"},
        {"confidence": 1.5},
        # displayed_mood must be the mood of the engine that was shown
        {"displayed_mood": "happy"},
        {"displayed_source": "backend", "displayed_mood": "calm"},
        {"on_device_mood": None},
    ],
)
def test_schema_rejects_invalid(overrides):
    with pytest.raises(ValidationError):
        ResultHistoryCreate(**_body(**overrides))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@pytest.fixture
def calls():
    return {}


@pytest.fixture
def client(monkeypatch, calls):
    async def fake_create(user_id, track_name, artist_name, mood_results, track_id=None):
        calls["create"] = {
            "user_id": str(user_id),
            "track_name": track_name,
            "artist_name": artist_name,
            "mood_results": mood_results,
            "track_id": track_id,
        }
        if calls.get("create_fails"):
            raise ValueError('relation "song_analyses" does not exist')
        return {"id": "row-1"}

    async def fake_list(user_id, limit=50, offset=0):
        calls["list_user_id"] = str(user_id)
        return calls.get("rows", [])

    async def fake_feedback(observation_ids, user_id):
        calls["feedback"] = {"ids": observation_ids, "user_id": user_id}
        if calls.get("feedback_fails"):
            raise ValueError("db down")
        return calls.get("answers", {})

    monkeypatch.setattr(crud_song_analysis, "create_song_analysis", fake_create)
    monkeypatch.setattr(crud_song_analysis, "get_user_song_analyses", fake_list)
    monkeypatch.setattr(crud_mood_observation, "get_feedback", fake_feedback)

    app = FastAPI()
    app.include_router(song_analysis.router, prefix="/api/v1/song")
    app.include_router(catalog.router, prefix="/api/v1/catalog")
    app.dependency_overrides[deps.get_current_user] = lambda: USER
    app.dependency_overrides[deps.optional_get_current_user] = lambda: USER
    return app


def test_post_saves_result_for_caller(client, calls):
    resp = TestClient(client).post("/api/v1/song/history", json=_body())

    assert resp.status_code == 201
    assert resp.json() == {"id": "row-1"}
    saved = calls["create"]
    assert saved["user_id"] == USER["id"]
    assert saved["track_name"] == "Inside Outside"
    assert saved["artist_name"] == ""
    assert saved["mood_results"]["backend_mood"] == "happy"
    assert saved["mood_results"]["on_device_mood"] == "calm"
    assert saved["mood_results"]["title_from_filename"] is False


def test_post_saves_title_from_filename(client, calls):
    resp = TestClient(client).post(
        "/api/v1/song/history", json=_body(title_from_filename=True)
    )

    assert resp.status_code == 201
    assert calls["create"]["mood_results"]["title_from_filename"] is True


def test_post_requires_auth(client):
    client.dependency_overrides.pop(deps.get_current_user)
    resp = TestClient(client).post("/api/v1/song/history", json=_body())

    assert resp.status_code in (401, 403)


def test_post_rejects_invalid_body(client, calls):
    resp = TestClient(client).post(
        "/api/v1/song/history", json=_body(displayed_mood="sad")
    )

    assert resp.status_code == 422
    assert "create" not in calls


def test_post_500_does_not_leak_storage_error(client, calls):
    calls["create_fails"] = True
    resp = TestClient(client).post("/api/v1/song/history", json=_body())

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Could not save to history"}


def _row(observation_id=None, **mood):
    return {
        "id": str(uuid4()),
        "user_id": USER["id"],
        "track_id": None,
        "track_name": "Song",
        "artist_name": "",
        "mood_results": {"primary_mood": "calm", "observation_id": observation_id, **mood},
        "created_at": "2026-10-16T20:00:00+00:00",
    }


def test_history_attaches_callers_feedback(client, calls):
    answered, unanswered = str(uuid4()), str(uuid4())
    calls["rows"] = [_row(answered), _row(unanswered), _row(None)]
    calls["answers"] = {answered: {"id": answered, "agrees": False, "user_mood": "reflective"}}

    resp = TestClient(client).get("/api/v1/song/history")

    assert resp.status_code == 200
    items = resp.json()["analyses"]
    assert (items[0]["agrees"], items[0]["user_mood"]) == (False, "reflective")
    assert (items[1]["agrees"], items[1]["user_mood"]) == (None, None)
    assert items[2]["agrees"] is None
    assert calls["list_user_id"] == USER["id"]
    assert calls["feedback"] == {"ids": [answered, unanswered], "user_id": USER["id"]}


def test_history_still_loads_when_feedback_fails(client, calls):
    calls["rows"] = [_row(str(uuid4()))]
    calls["feedback_fails"] = True

    resp = TestClient(client).get("/api/v1/song/history")

    assert resp.status_code == 200
    assert resp.json()["analyses"][0]["agrees"] is None


def test_history_rejects_feedback_outside_the_four_buckets(client, calls):
    """user_mood follows the feedback contract (UserMood), not any string."""
    from app.schemas.song_analysis import SongAnalysisHistoryItem

    row = _row()
    with pytest.raises(ValidationError):
        SongAnalysisHistoryItem(
            id=row["id"],
            user_id=row["user_id"],
            track_name="Song",
            artist_name="",
            mood_results={},
            created_at=row["created_at"],
            user_mood="happy",
        )


def test_history_handles_legacy_rows_without_observation(client, calls):
    legacy = _row()
    legacy["mood_results"] = {"primary_mood": "happy", "confidence": 0.7}
    calls["rows"] = [legacy]

    resp = TestClient(client).get("/api/v1/song/history")

    assert resp.status_code == 200
    assert calls["feedback"]["ids"] == []


# ---------------------------------------------------------------------------
# Catalog opt-out
# ---------------------------------------------------------------------------


FEATURES = {
    "tempo": 120.0,
    "beat_strength": 0.5,
    "spectral_centroid": 2000.0,
    "spectral_rolloff": 4000.0,
    "spectral_bandwidth": 1500.0,
    "harmonic_ratio": 0.5,
    "zero_crossing_rate": 0.1,
    "rms_energy": 0.1,
    "dynamic_range": 0.1,
    "mfcc_mean": [0.0, 0.0, 0.0],
    "duration_seconds": 30.0,
    "energy_label": "Medium (0.10)",
    "brightness_label": "Warm",
    "texture_label": "Textured",
}


class _FakeResponse:
    content = b"fake-mp3"

    def raise_for_status(self):
        pass


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        return _FakeResponse()


@pytest.fixture
def catalog_client(client, monkeypatch):
    monkeypatch.setattr(catalog.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(
        audio_analysis_service,
        "analyze_uploaded_audio",
        lambda file_data, filename: FEATURES,
    )
    return TestClient(client)


def _catalog_body(**overrides) -> dict:
    body = {
        "audio_url": "https://example.com/t.mp3",
        "track_id": "123",
        "track_name": "Planet 21",
        "artist_name": "Someone",
    }
    body.update(overrides)
    return body


def test_catalog_saves_history_by_default(catalog_client, calls):
    resp = catalog_client.post("/api/v1/catalog/analyze", json=_catalog_body())

    assert resp.status_code == 200
    assert calls["create"]["track_name"] == "Planet 21"


def test_catalog_never_saves_history_for_guests(client, catalog_client, calls):
    client.dependency_overrides[deps.optional_get_current_user] = lambda: None
    resp = catalog_client.post("/api/v1/catalog/analyze", json=_catalog_body())

    assert resp.status_code == 200
    assert "create" not in calls


def test_catalog_skips_history_when_app_saves_it(catalog_client, calls):
    resp = catalog_client.post(
        "/api/v1/catalog/analyze", json=_catalog_body(save_to_history=False)
    )

    assert resp.status_code == 200
    assert "create" not in calls


# ---------------------------------------------------------------------------
# CRUD: feedback lookup is scoped to the caller
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, db):
        self.db = db

    def select(self, columns):
        self.db["select"] = columns
        return self

    def in_(self, field, values):
        self.db["in"] = (field, values)
        return self

    def eq(self, field, value):
        self.db["eq"] = (field, value)
        return self

    def execute(self):
        class _Resp:
            error = None
            data = [{"id": "o1", "agrees": True, "user_mood": None}]

        return _Resp()


class _FakeSupabase:
    def __init__(self):
        self.db = {}

    def table(self, name):
        self.db["table"] = name
        return _FakeQuery(self.db)


@pytest.mark.asyncio
async def test_crud_feedback_is_scoped_to_user(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(crud_mood_observation, "_supabase", fake)

    result = await crud_mood_observation.get_feedback(["o1"], user_id="user-1")

    assert result == {"o1": {"id": "o1", "agrees": True, "user_mood": None}}
    assert fake.db["table"] == "mood_observations"
    assert fake.db["in"] == ("id", ["o1"])
    assert fake.db["eq"] == ("user_id", "user-1")


@pytest.mark.asyncio
async def test_crud_feedback_skips_query_without_ids(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(crud_mood_observation, "_supabase", fake)

    assert await crud_mood_observation.get_feedback([], user_id="user-1") == {}
    assert "table" not in fake.db
