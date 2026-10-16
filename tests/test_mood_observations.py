from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import deps
from app.api.v1 import app_config, mood_observations
from app.core import config as config_module
from app.crud import mood_observation as crud
from app.schemas.mood_observation import MoodFeedbackUpdate, MoodObservationCreate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _body(**overrides) -> dict:
    body = {
        "id": str(uuid4()),
        "source": "upload",
        "analysis_id": "an-1",
        "backend_mood": "happy",
        "on_device_mood": "calm",
        "on_device_tags": ["vocals", "piano"],
        "on_device_probabilities": {"happy": 0.2, "calm": 0.8},
        "on_device_latency_ms": 840,
        "on_device_error": None,
        "displayed_mood": "calm",
        "displayed_source": "on_device",
        "platform": "ios",
        "os_version": "18.1",
        "device_model": "iPhone15,2",
        "app_version": "1.0.0+7",
    }
    body.update(overrides)
    return body


@pytest.fixture
def calls():
    return {}


@pytest.fixture
def client(monkeypatch, calls):
    """App with only the routers under test; crud + auth are faked."""

    async def fake_upsert(observation, user_id=None):
        calls["upsert"] = {"observation": observation, "user_id": user_id}
        return observation

    async def fake_feedback(observation_id, agrees, user_mood):
        calls["feedback"] = {
            "id": observation_id,
            "agrees": agrees,
            "user_mood": user_mood,
        }
        if calls.get("feedback_row_missing"):
            return None
        return {"id": str(observation_id)}

    monkeypatch.setattr(crud, "upsert_mood_observation", fake_upsert)
    monkeypatch.setattr(crud, "update_mood_feedback", fake_feedback)

    app = FastAPI()
    app.include_router(mood_observations.router, prefix="/api/v1/mood-observations")
    app.include_router(app_config.router, prefix="/api/v1")
    app.dependency_overrides[deps.optional_get_current_user] = lambda: calls.get(
        "user"
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_schema_accepts_full_body():
    obs = MoodObservationCreate(**_body())
    row = obs.to_row()
    assert row["on_device_tags"] == ["vocals", "piano"]
    assert isinstance(row["id"], str)
    assert "agrees" not in row and "user_mood" not in row and "user_id" not in row


def test_schema_minimal_backend_only_body():
    obs = MoodObservationCreate(
        id=uuid4(),
        source="catalog",
        backend_mood="sad",
        displayed_mood="sad",
        displayed_source="backend",
        on_device_error="decode_failed",
    )
    assert obs.on_device_tags == []
    assert obs.on_device_mood is None


def test_schema_ignores_unknown_fields_like_titles():
    obs = MoodObservationCreate(**_body(title="Secret Song", filename="a.mp3"))
    row = obs.to_row()
    assert "title" not in row and "filename" not in row


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "not-a-uuid"},
        {"source": "spotify"},
        {"displayed_source": "server"},
        {"backend_mood": ""},
        {"displayed_mood": "x" * 101},
        {"analysis_id": "x" * 101},
        {"platform": "x" * 101},
        {"on_device_tags": [f"t{i}" for i in range(11)]},
        {"on_device_tags": ["x" * 41]},
        {"on_device_probabilities": {f"m{i}": 0.1 for i in range(11)}},
        {"on_device_probabilities": {"happy": 1.5}},
        {"on_device_error": "e" * 501},
        {"on_device_latency_ms": -1},
        {"displayed_source": "on_device", "on_device_mood": None},
    ],
)
def test_schema_rejects_invalid(overrides):
    with pytest.raises(ValidationError):
        MoodObservationCreate(**_body(**overrides))


def test_schema_accepts_limits():
    MoodObservationCreate(
        **_body(
            on_device_tags=["x" * 40] * 10,
            on_device_probabilities={f"m{i}": 0.1 for i in range(10)},
            on_device_error="e" * 500,
            device_model="x" * 100,
        )
    )


@pytest.mark.parametrize("mood", ["upbeat", "serene", "charged", "reflective", None])
def test_feedback_schema_accepts_buckets(mood):
    assert MoodFeedbackUpdate(agrees=mood is None, user_mood=mood).user_mood == mood


def test_feedback_schema_rejects_backend_labels():
    with pytest.raises(ValidationError):
        MoodFeedbackUpdate(agrees=False, user_mood="happy")


# ---------------------------------------------------------------------------
# POST /mood-observations
# ---------------------------------------------------------------------------


def test_post_records_guest_observation(client, calls):
    body = _body()
    resp = client.post("/api/v1/mood-observations", json=body)

    assert resp.status_code == 201
    assert resp.json() == {"id": body["id"]}
    assert calls["upsert"]["user_id"] is None
    assert calls["upsert"]["observation"]["backend_mood"] == "happy"
    assert calls["upsert"]["observation"]["on_device_probabilities"] == {
        "happy": 0.2,
        "calm": 0.8,
    }


def test_post_attributes_signed_in_user(client, calls):
    calls["user"] = {"id": "user-123", "email": "a@b.c"}
    resp = client.post("/api/v1/mood-observations", json=_body())

    assert resp.status_code == 201
    assert calls["upsert"]["user_id"] == "user-123"


def test_post_rejects_invalid_body(client, calls):
    resp = client.post("/api/v1/mood-observations", json=_body(source="radio"))

    assert resp.status_code == 422
    assert "upsert" not in calls


def test_post_returns_500_when_storage_fails(client, monkeypatch):
    async def boom(observation, user_id=None):
        raise ValueError("db down")

    monkeypatch.setattr(crud, "upsert_mood_observation", boom)
    resp = client.post("/api/v1/mood-observations", json=_body())

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PATCH /mood-observations/{id}/feedback
# ---------------------------------------------------------------------------


def test_patch_feedback_disagree_with_bucket(client, calls):
    obs_id = str(uuid4())
    resp = client.patch(
        f"/api/v1/mood-observations/{obs_id}/feedback",
        json={"agrees": False, "user_mood": "serene"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"id": obs_id, "agrees": False, "user_mood": "serene"}
    assert calls["feedback"]["agrees"] is False
    assert calls["feedback"]["user_mood"] == "serene"
    assert str(calls["feedback"]["id"]) == obs_id


def test_patch_feedback_agree_without_bucket(client, calls):
    resp = client.patch(
        f"/api/v1/mood-observations/{uuid4()}/feedback", json={"agrees": True}
    )

    assert resp.status_code == 200
    assert calls["feedback"]["user_mood"] is None


def test_patch_feedback_404_when_missing(client, calls):
    calls["feedback_row_missing"] = True
    resp = client.patch(
        f"/api/v1/mood-observations/{uuid4()}/feedback", json={"agrees": True}
    )

    assert resp.status_code == 404


def test_patch_feedback_rejects_bad_id_and_mood(client):
    assert (
        client.patch(
            "/api/v1/mood-observations/nope/feedback", json={"agrees": True}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/mood-observations/{uuid4()}/feedback",
            json={"agrees": False, "user_mood": "sad"},
        ).status_code
        == 422
    )


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("enabled", [True, False])
def test_config_reports_kill_switch(client, monkeypatch, enabled):
    monkeypatch.setattr(config_module.settings, "ON_DEVICE_MOOD_ENABLED", enabled)
    resp = client.get("/api/v1/config")

    assert resp.status_code == 200
    assert resp.json() == {"on_device_mood": enabled}


def test_config_defaults_to_enabled():
    assert config_module.Settings.model_fields["ON_DEVICE_MOOD_ENABLED"].default is True


def test_routes_registered_on_v1_router():
    from app.api.v1.api import api_router

    paths = {route.path for route in api_router.routes}
    assert "/mood-observations" in paths
    assert "/mood-observations/{observation_id}/feedback" in paths
    assert "/config" in paths


# ---------------------------------------------------------------------------
# CRUD (fake Supabase client)
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, data):
        self.data = data
        self.error = None


class _FakeTable:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self._op = None
        self._payload = None
        self._eq = None

    def upsert(self, payload, on_conflict=""):
        self._op, self._payload = "upsert", payload
        self.db.setdefault("upsert_on_conflict", on_conflict)
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def eq(self, field, value):
        self._eq = (field, value)
        return self

    def execute(self):
        self.db["table"] = self.name
        rows = self.db.setdefault("rows", {})
        if self._op == "upsert":
            existing = rows.get(self._payload["id"], {})
            existing.update(self._payload)
            rows[self._payload["id"]] = existing
            self.db["last_upsert"] = self._payload
            return _FakeResp([existing])
        _, value = self._eq
        if value not in rows:
            return _FakeResp([])
        rows[value].update(self._payload)
        return _FakeResp([rows[value]])


class _FakeSupabase:
    def __init__(self):
        self.db = {}

    def table(self, name):
        return _FakeTable(self.db, name)


@pytest.fixture
def fake_supabase(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(crud, "_supabase", fake)
    return fake


@pytest.mark.asyncio
async def test_crud_upsert_writes_observation_without_feedback(fake_supabase):
    row = MoodObservationCreate(**_body()).to_row()
    saved = await crud.upsert_mood_observation(row)

    payload = fake_supabase.db["last_upsert"]
    assert fake_supabase.db["table"] == "mood_observations"
    assert fake_supabase.db["upsert_on_conflict"] == "id"
    assert "user_id" not in payload
    assert "agrees" not in payload and "feedback_at" not in payload
    assert payload["updated_at"]
    assert saved["id"] == row["id"]


@pytest.mark.asyncio
async def test_crud_upsert_sets_user_id_when_known(fake_supabase):
    row = MoodObservationCreate(**_body()).to_row()
    await crud.upsert_mood_observation(row, user_id="user-1")

    assert fake_supabase.db["last_upsert"]["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_crud_retry_keeps_existing_feedback(fake_supabase):
    row = MoodObservationCreate(**_body()).to_row()
    await crud.upsert_mood_observation(row)
    await crud.update_mood_feedback(row["id"], agrees=True, user_mood=None)
    saved = await crud.upsert_mood_observation(row)

    assert saved["agrees"] is True
    assert saved["feedback_at"]


@pytest.mark.asyncio
async def test_crud_feedback_returns_none_for_unknown_id(fake_supabase):
    assert await crud.update_mood_feedback(uuid4(), agrees=False, user_mood="serene") is None
