from datetime import datetime, timezone
from uuid import UUID
import asyncio
from typing import Optional
from app.core.supabase import get_supabase_service_client

_supabase = get_supabase_service_client()


async def create_state(state: str, user_id: UUID, expires_at: datetime) -> None:
    loop = asyncio.get_running_loop()

    def _insert():
        _supabase.table("spotify_oauth_states").insert(
            {
                "state": state,
                "user_id": str(user_id),
                "expires_at": expires_at.isoformat(),
            }
        ).execute()

    await loop.run_in_executor(None, _insert)


async def get_state(state: str) -> Optional[dict]:
    """
    Fetch a state record. If expired, delete and return None.
    """
    loop = asyncio.get_running_loop()

    def _fetch():
        resp = (
            _supabase.table("spotify_oauth_states")
            .select("*")
            .eq("state", state)
            .maybe_single()
            .execute()
        )
        if not resp or resp.data is None:
            return None
        if getattr(resp, "error", None):
            raise ValueError(resp.error.message)
        return resp.data

    record = await loop.run_in_executor(None, _fetch)
    if not record:
        return None

    expires_at = record.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        await delete_state(state)
        return None

    return record


async def delete_state(state: str) -> bool:
    loop = asyncio.get_running_loop()

    def _delete():
        resp = (
            _supabase.table("spotify_oauth_states")
            .delete()
            .eq("state", state)
            .execute()
        )
        return resp.data

    data = await loop.run_in_executor(None, _delete)
    return bool(data)

