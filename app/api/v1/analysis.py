from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID
from typing import List, Dict, Any
from app.api.deps import get_current_user
from app.crud import analysis as crud_analysis
from app.schemas import analysis as schemas_analysis
from app.services import spotify_api
from app.services.analysis_service import analyze_playlist_mood

router = APIRouter()


# Constants for track limits
MIN_TRACKS = 5
DEFAULT_TRACK_LIMIT = 50
MAX_TRACK_LIMIT = 100


def extract_track_metadata(track_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Extract track metadata (name, artists) from Spotify playlist items.
    
    Args:
        track_items: List of playlist track items from Spotify API
        
    Returns:
        Dict mapping track_id to {name, artists}
    """
    metadata = {}
    for item in track_items:
        track = item.get("track")
        if not track or not track.get("id"):
            continue
        
        track_id = track["id"]
        metadata[track_id] = {
            "name": track.get("name", "Unknown Track"),
            "artists": [artist.get("name", "Unknown Artist") for artist in track.get("artists", [])],
        }
    
    return metadata


@router.post("/analyze/{playlist_id}", response_model=schemas_analysis.PlaylistAnalysisResponse)
async def analyze_playlist(
    playlist_id: str,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(DEFAULT_TRACK_LIMIT, ge=MIN_TRACKS, le=MAX_TRACK_LIMIT,
                       description="Number of tracks to analyze (min 5, max 100)"),
):
    """
    Analyze a playlist's mood.
    Fetches tracks, gets audio features, and calculates mood.
    
    - Analyzes up to `limit` tracks (default 50)
    - Requires minimum 5 tracks for meaningful analysis
    - Returns mood classification, distribution, confidence, and top tracks
    """
    user_id = UUID(current_user["id"])
    
    try:
        # Get valid access token
        access_token = await spotify_api.get_valid_spotify_token(user_id)
        
        # Get playlist info
        playlist_info = await spotify_api.get_playlist_info(access_token, playlist_id)
        playlist_name = playlist_info.get("name", "Unknown Playlist")
        
        # Get playlist tracks (fetch up to limit)
        tracks_data = await spotify_api.get_playlist_tracks(access_token, playlist_id, limit=limit)
        
        # Extract track items
        track_items = tracks_data.get("items", [])
        
        # Filter valid tracks and extract IDs
        valid_items = [item for item in track_items if item.get("track") and item["track"].get("id")]
        track_ids = [item["track"]["id"] for item in valid_items]
        
        if not track_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Playlist has no tracks",
            )
        
        # Validate minimum track count
        if len(track_ids) < MIN_TRACKS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Playlist must have at least {MIN_TRACKS} tracks for meaningful analysis. Found {len(track_ids)} tracks.",
            )
        
        # Apply limit (in case API returned more)
        track_ids = track_ids[:limit]
        valid_items = valid_items[:limit]
        
        # Extract track metadata for top tracks display
        track_metadata = extract_track_metadata(valid_items)
        
        # Get audio features in batches (max 100 per request)
        all_audio_features = []
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i : i + 100]
            features_data = await spotify_api.get_audio_features(access_token, batch)
            all_audio_features.extend(features_data.get("audio_features", []))
        
        # Analyze mood with track metadata
        mood_results = analyze_playlist_mood(all_audio_features, track_metadata)
        
        # Save analysis
        analysis = await crud_analysis.create_playlist_analysis(
            user_id, playlist_id, playlist_name, mood_results
        )
        
        return analysis
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze playlist: {str(e)}",
        )


@router.get("/history", response_model=schemas_analysis.AnalysisHistoryResponse)
async def get_analysis_history(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get user's analysis history."""
    user_id = UUID(current_user["id"])
    analyses = await crud_analysis.get_user_analyses(
        user_id, limit=limit, offset=offset
    )
    
    return schemas_analysis.AnalysisHistoryResponse(
        analyses=analyses,
        total=len(analyses),
    )


@router.get("/{analysis_id}", response_model=schemas_analysis.PlaylistAnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific analysis by ID."""
    user_id = UUID(current_user["id"])
    analysis = await crud_analysis.get_playlist_analysis(analysis_id)
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    # Verify ownership - analysis is a dict from Supabase
    analysis_user_id = analysis.get("user_id")
    if str(analysis_user_id) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this analysis",
        )
    
    return analysis
