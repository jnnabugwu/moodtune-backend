from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import asyncio
from app.core.supabase import get_supabase_service_client

# Use the Supabase service client so we can write to tables.
_supabase = get_supabase_service_client()


async def get_spotify_connection(
    user_id: UUID,
) -> Optional[dict]:
    """Get Spotify connection for a user."""
    loop = asyncio.get_running_loop()

    def _fetch():
        resp = (
            _supabase.table("spotify_connections")
            .select("*")
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )
        if not resp or resp.data is None:
            return None
        if getattr(resp, "error", None):
            raise ValueError(resp.error.message)
        return resp.data

    return await loop.run_in_executor(None, _fetch)


async def create_spotify_connection(
    user_id: UUID,
    spotify_user_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> dict:
    """Create a new Spotify connection."""
    loop = asyncio.get_running_loop()

    def _insert():
        resp = (
            _supabase.table("spotify_connections")
            .insert(
                {
                    "user_id": str(user_id),
                    "spotify_user_id": spotify_user_id,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at.isoformat(),
                }
            )
            .execute()
        )
        data = resp.data or []
        return data[0] if data else None

    return await loop.run_in_executor(None, _insert)


async def update_spotify_connection(
    connection: dict,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> dict:
    """Update an existing Spotify connection."""
    loop = asyncio.get_running_loop()
    updates = {
        "access_token": access_token,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if refresh_token:
        updates["refresh_token"] = refresh_token
    if expires_at:
        updates["expires_at"] = expires_at.isoformat()

    def _update():
        resp = (
            _supabase.table("spotify_connections")
            .update(updates)
            .eq("id", connection["id"])
            .execute()
        )
        data = resp.data or []
        return data[0] if data else connection

    return await loop.run_in_executor(None, _update)


async def delete_spotify_connection(
) -> bool:
    """Delete Spotify connection by id."""
    # This helper now expects a connection dict; keeping a simple version for API use
    raise NotImplementedError("Use delete_spotify_connection_by_user instead.")


async def delete_spotify_connection_by_user(
    user_id: UUID,
) -> bool:
    """Delete Spotify connection for a user."""
    loop = asyncio.get_running_loop()

    def _delete():
        resp = (
            _supabase.table("spotify_connections")
            .delete()
            .eq("user_id", str(user_id))
            .execute()
        )
        return resp.data

    data = await loop.run_in_executor(None, _delete)
    return bool(data)
