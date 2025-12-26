import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.spotify_connection import SpotifyConnection
from app.services.spotify_auth import refresh_access_token


async def get_valid_spotify_token(user_id: Union[str, UUID], db: AsyncSession) -> str:
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
    # Get connection from database
    stmt = select(SpotifyConnection).where(SpotifyConnection.user_id == user_id)
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise ValueError("No Spotify connection found for user")
    
    # Check if token needs refresh
    if datetime.now(timezone.utc) >= connection.expires_at:
        # Refresh token
        token_data = await refresh_access_token(connection.refresh_token)
        connection.access_token = token_data["access_token"]
        connection.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )
        # Update refresh token if provided (Spotify sometimes returns new one)
        if "refresh_token" in token_data:
            connection.refresh_token = token_data["refresh_token"]
        connection.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(connection)
    
    return connection.access_token


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

