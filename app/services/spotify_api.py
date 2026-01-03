import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Union
from uuid import UUID
import asyncio
from app.core.supabase import get_supabase_service_client
from app.services.spotify_auth import refresh_access_token

_supabase = get_supabase_service_client()


async def get_valid_spotify_token(user_id: Union[str, UUID]) -> str:
    """
    Get valid Spotify token for user, refreshing if needed.
    
    Args:
        user_id: Supabase user ID (UUID)
        db: Database session
        
    Returns:
        str: Valid access token
        
    Raises:
        ValueError: If no Spotify connection exists for user
    """
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

    connection = await loop.run_in_executor(None, _fetch)

    if not connection:
        raise ValueError("No Spotify connection found for user")

    # Parse expires_at
    expires_at_str = connection.get("expires_at")
    expires_at = (
        datetime.fromisoformat(expires_at_str)
        if isinstance(expires_at_str, str)
        else expires_at_str
    )

    if datetime.now(timezone.utc) >= expires_at:
        token_data = await refresh_access_token(connection["refresh_token"])
        new_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )

        def _update():
            resp = (
                _supabase.table("spotify_connections")
                .update(
                    {
                        "access_token": token_data["access_token"],
                        "expires_at": new_expires_at.isoformat(),
                        "refresh_token": token_data.get(
                            "refresh_token", connection["refresh_token"]
                        ),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .eq("id", connection["id"])
                .execute()
            )
            data = resp.data or []
            return data[0] if data else connection

        connection = await loop.run_in_executor(None, _update)

    return connection["access_token"]


async def get_user_playlists(access_token: str, limit: int = 50, offset: int = 0) -> Dict:
    """
    Get user's playlists from Spotify.
    
    Args:
        access_token: Valid Spotify access token
        limit: Maximum number of playlists to return
        offset: Offset for pagination
        
    Returns:
        dict: Spotify API response with playlists
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.spotify.com/v1/me/playlists",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return response.json()


async def get_user_profile(access_token: str) -> Dict:
    """
    Get the current user's Spotify profile.

    Args:
        access_token: Valid Spotify access token

    Returns:
        dict: Spotify API response with user profile
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def get_playlist_info(access_token: str, playlist_id: str) -> Dict:
    """
    Get playlist information.
    
    Args:
        access_token: Valid Spotify access token
        playlist_id: Spotify playlist ID
        
    Returns:
        dict: Spotify API response with playlist info
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def get_playlist_tracks(
    access_token: str, playlist_id: str, limit: int = 100, offset: int = 0
) -> Dict:
    """
    Get tracks from a specific playlist.
    
    Args:
        access_token: Valid Spotify access token
        playlist_id: Spotify playlist ID
        limit: Maximum number of tracks to return
        offset: Offset for pagination
        
    Returns:
        dict: Spotify API response with tracks
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        return response.json()


async def get_audio_features(access_token: str, track_ids: List[str]) -> Dict:
    """
    Get audio features for multiple tracks.
    
    Args:
        access_token: Valid Spotify access token
        track_ids: List of Spotify track IDs (max 100)
        
    Returns:
        dict: Spotify API response with audio features
    """
    if len(track_ids) > 100:
        raise ValueError("Maximum 100 track IDs allowed per request")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.spotify.com/v1/audio-features",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"ids": ",".join(track_ids)},
        )
        response.raise_for_status()
        return response.json()

