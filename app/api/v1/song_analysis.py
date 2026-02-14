import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from uuid import UUID
from typing import List, Dict, Any, Optional
import httpx
import sentry_sdk
from app.api.deps import get_current_user
from app.core.config import settings
from app.schemas import song_analysis as schemas_song
from app.services import spotify_api
from app.services.audio_analysis_service import audio_analysis_service

router = APIRouter()


def extract_track_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract track info from Spotify playlist track item."""
    track = item.get("track", {})
    if not track or not track.get("id"):
        return None

    # Get album image
    album = track.get("album", {})
    images = album.get("images", [])
    image_url = images[0].get("url") if images else None

    # Get artists
    artists = [artist.get("name", "Unknown Artist") for artist in track.get("artists", [])]

    return {
        "id": track["id"],
        "name": track.get("name", "Unknown Track"),
        "artists": artists,
        "preview_url": track.get("preview_url"),
        "image_url": image_url,
        "duration_ms": track.get("duration_ms"),
    }


@router.get("/playlist/{playlist_id}/tracks", response_model=schemas_song.PlaylistTracksResponse)
async def get_playlist_tracks(
    playlist_id: str,
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
):
    """
    Get first N tracks from a playlist for song selection.
    Returns tracks with preview URLs for analysis.
    """
    user_id = UUID(current_user["id"])

    try:
        # Get valid access token
        access_token = await spotify_api.get_valid_spotify_token(user_id)

        # Get playlist tracks
        tracks_data = await spotify_api.get_playlist_tracks(
            access_token, playlist_id, limit=limit, offset=0
        )

        # Extract track items
        track_items = tracks_data.get("items", [])
        total = tracks_data.get("total", 0)

        # Extract track info
        tracks = []
        for item in track_items:
            track_info = extract_track_from_item(item)
            if track_info:
                tracks.append(schemas_song.PlaylistTrack(**track_info))

        return schemas_song.PlaylistTracksResponse(tracks=tracks, total=total)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found or you don't have access to it",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Spotify API error: {e.response.status_code} - {e.response.text[:200]}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch playlist tracks: {str(e)}",
        )


@router.post("/analyze", response_model=schemas_song.SongAnalysisResponse)
async def analyze_song(
    current_user: dict = Depends(get_current_user),
    audio_file: UploadFile = File(...),
    track_name: Optional[str] = Form(default=None),
    artist_name: Optional[str] = Form(default=None),
    track_id: Optional[str] = Form(default=None),
):
    """
    Analyze a single song's mood from uploaded/downloaded audio.
    Uses librosa on the audio file and returns mood classification and audio features.
    """
    if not audio_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is required",
        )
    ext = os.path.splitext(audio_file.filename)[1].lstrip(".").lower()
    if ext not in settings.ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {ext}",
        )
    file_data = await audio_file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    name = track_name or audio_file.filename or "Unknown Track"
    artist = artist_name or "Unknown Artist"

    sentry_sdk.set_context(
        "song_request",
        {"track_id": track_id, "track_name": name, "artist_name": artist},
    )
    sentry_sdk.add_breadcrumb(
        category="analysis",
        message=f"Analyze song request: {name} - {artist}",
        level="info",
    )

    try:
        features = audio_analysis_service.analyze_audio_bytes(
            file_data=file_data,
            filename=audio_file.filename,
        )
        mood = audio_analysis_service.determine_mood(features)

        response = schemas_song.SongAnalysisResponse(
            track_name=name,
            artist_name=artist,
            track_id=track_id,
            mood=schemas_song.MoodResult(**mood),
            features=schemas_song.AudioFeatures(**features),
            success=True,
            message=f"Analysis complete: {mood['primary_mood']} mood detected",
        )
        sentry_sdk.add_breadcrumb(
            category="analysis",
            message=f"Analysis complete: {mood['primary_mood']}",
            level="info",
        )
        return response

    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )


@router.post("/analyze/{track_id}", response_model=schemas_song.SongAnalysisResponse)
async def analyze_song_by_id(
    track_id: str,
    current_user: dict = Depends(get_current_user),
    audio_file: UploadFile = File(...),
):
    """
    Analyze a song by track ID using your own audio file.
    Fetches track metadata (name, artist) from Spotify; analysis is done with librosa on the uploaded file.
    """
    if not audio_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is required",
        )
    ext = os.path.splitext(audio_file.filename)[1].lstrip(".").lower()
    if ext not in settings.ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {ext}",
        )
    file_data = await audio_file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    track_name = "Unknown Track"
    artist_name = "Unknown Artist"
    user_id = UUID(current_user["id"])
    try:
        access_token = await spotify_api.get_valid_spotify_token(user_id)
        track_info = await spotify_api.get_track_info(access_token, track_id)
        track_name = track_info.get("name", track_name)
        artists = track_info.get("artists", [])
        artist_name = artists[0].get("name", artist_name) if artists else artist_name
    except (ValueError, httpx.HTTPStatusError):
        pass  # use defaults if Spotify metadata unavailable

    sentry_sdk.set_context(
        "song_request",
        {"track_id": track_id, "track_name": track_name, "artist_name": artist_name},
    )
    sentry_sdk.add_breadcrumb(
        category="analysis",
        message=f"Analyze song by id: {track_id}",
        level="info",
    )

    try:
        features = audio_analysis_service.analyze_audio_bytes(
            file_data=file_data,
            filename=audio_file.filename,
        )
        mood = audio_analysis_service.determine_mood(features)

        return schemas_song.SongAnalysisResponse(
            track_name=track_name,
            artist_name=artist_name,
            track_id=track_id,
            mood=schemas_song.MoodResult(**mood),
            features=schemas_song.AudioFeatures(**features),
            success=True,
            message=f"Analysis complete: {mood['primary_mood']} mood detected",
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )
