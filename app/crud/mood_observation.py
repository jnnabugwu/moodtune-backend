import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from supabase import Client

from app.core.supabase import get_supabase_service_client

_TABLE = "mood_observations"
_supabase: Optional[Client] = None


def _client() -> Client:
    """Service-role client, created on first use (keeps imports side-effect free)."""
    global _supabase
    if _supabase is None:
        _supabase = get_supabase_service_client()
    return _supabase


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def upsert_mood_observation(
    observation: dict, user_id: Optional[str] = None
) -> Optional[dict]:
    """
    Insert or update a mood observation by its client-generated id.

    Only the observation columns are written, so a retry never clears
    feedback already recorded. user_id is only written when known, so an
    unauthenticated retry never strips attribution.
    """
    loop = asyncio.get_running_loop()
    row = {**observation, "updated_at": _now()}
    if user_id is not None:
        row["user_id"] = str(user_id)

    def _upsert():
        resp = _client().table(_TABLE).upsert(row, on_conflict="id").execute()
        if getattr(resp, "error", None):
            raise ValueError(resp.error.message)
        data = resp.data or []
        return data[0] if data else None

    return await loop.run_in_executor(None, _upsert)


async def update_mood_feedback(
    observation_id: UUID, agrees: bool, user_mood: Optional[str]
) -> Optional[dict]:
    """Record the user's answer. Returns None when no row has this id."""
    loop = asyncio.get_running_loop()
    now = _now()
    updates = {
        "agrees": agrees,
        "user_mood": user_mood,
        "feedback_at": now,
        "updated_at": now,
    }

    def _update():
        resp = (
            _client()
            .table(_TABLE)
            .update(updates)
            .eq("id", str(observation_id))
            .execute()
        )
        if getattr(resp, "error", None):
            raise ValueError(resp.error.message)
        data = resp.data or []
        return data[0] if data else None

    return await loop.run_in_executor(None, _update)
