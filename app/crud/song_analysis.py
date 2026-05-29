import asyncio
from typing import List, Optional
from uuid import UUID
from app.core.supabase import get_supabase_service_client

_supabase = get_supabase_service_client()


async def create_song_analysis(
    user_id: UUID,
    track_name: str,
    artist_name: str,
    mood_results: dict,
    track_id: Optional[str] = None,
) -> dict:
    """Save a song analysis result to Supabase."""
    loop = asyncio.get_running_loop()

    def _insert():
        resp = (
            _supabase.table("song_analyses")
            .insert(
                {
                    "user_id": str(user_id),
                    "track_id": track_id,
                    "track_name": track_name,
                    "artist_name": artist_name,
                    "mood_results": mood_results,
                }
            )
            .execute()
        )
        data = resp.data or []
        return data[0] if data else None

    return await loop.run_in_executor(None, _insert)


async def get_user_song_analyses(
    user_id: UUID, limit: int = 50, offset: int = 0
) -> List[dict]:
    """Get all song analyses for a user from Supabase, newest first."""
    loop = asyncio.get_running_loop()

    def _fetch():
        resp = (
            _supabase.table("song_analyses")
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


async def get_song_analysis(analysis_id: UUID) -> Optional[dict]:
    """Get a specific song analysis by ID."""
    loop = asyncio.get_running_loop()

    def _fetch():
        resp = (
            _supabase.table("song_analyses")
            .select("*")
            .eq("id", str(analysis_id))
            .maybe_single()
            .execute()
        )
        if getattr(resp, "error", None):
            raise ValueError(resp.error.message)
        return resp.data

    return await loop.run_in_executor(None, _fetch)
