import asyncio
from typing import List, Optional
from uuid import UUID
from app.core.supabase import get_supabase_service_client

_supabase = get_supabase_service_client()


async def create_playlist_analysis(
    user_id: UUID,
    playlist_id: str,
    playlist_name: str,
    mood_results: dict,
) -> dict:
    """Create a new playlist analysis in Supabase."""
    loop = asyncio.get_running_loop()

    def _insert():
        resp = (
            _supabase.table("playlist_analyses")
            .insert(
                {
                    "user_id": str(user_id),
                    "playlist_id": playlist_id,
                    "playlist_name": playlist_name,
                    "mood_results": mood_results,
                }
            )
            .execute()
        )
        data = resp.data or []
        return data[0] if data else None

    return await loop.run_in_executor(None, _insert)


async def get_playlist_analysis(analysis_id: UUID) -> Optional[dict]:
    """Get a specific playlist analysis by ID from Supabase."""
    loop = asyncio.get_running_loop()

    def _fetch():
        resp = (
            _supabase.table("playlist_analyses")
            .select("*")
            .eq("id", str(analysis_id))
            .maybe_single()
            .execute()
        )
        if getattr(resp, "error", None):
            raise ValueError(resp.error.message)
        return resp.data

    return await loop.run_in_executor(None, _fetch)


async def get_user_analyses(
    user_id: UUID, limit: int = 50, offset: int = 0
) -> List[dict]:
    """Get all analyses for a user from Supabase, newest first."""
    loop = asyncio.get_running_loop()

    def _fetch():
        resp = (
            _supabase.table("playlist_analyses")
            .select("*")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        if getattr(resp, "error", None):
            raise ValueError(resp.error.message)
        return resp.data or []

    return await loop.run_in_executor(None, _fetch)
