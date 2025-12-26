from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import analysis as crud_analysis
from app.schemas import analysis as schemas_analysis
from app.services import spotify_api
from app.services.analysis_service import analyze_playlist_mood

router = APIRouter()


@router.post("/analyze/{playlist_id}", response_model=schemas_analysis.PlaylistAnalysisResponse)
async def analyze_playlist(
    playlist_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a playlist's mood.
    Fetches tracks, gets audio features, and calculates mood.
    """
    user_id = UUID(current_user["id"])
    
    try:
        # Get valid access token
        access_token = await spotify_api.get_valid_spotify_token(user_id, db)
        
        # Get playlist info
        playlist_info = await spotify_api.get_playlist_info(access_token, playlist_id)
        playlist_name = playlist_info.get("name", "Unknown Playlist")
        
        # Get playlist tracks
        tracks_data = await spotify_api.get_playlist_tracks(access_token, playlist_id)
        
        # Extract track IDs
        track_items = tracks_data.get("items", [])
        track_ids = [
            item["track"]["id"]
            for item in track_items
            if item.get("track") and item["track"].get("id")
        ]
        
        if not track_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Playlist has no tracks",
            )
        
        # Get audio features in batches (max 100 per request)
        all_audio_features = []
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i : i + 100]
            features_data = await spotify_api.get_audio_features(access_token, batch)
            all_audio_features.extend(features_data.get("audio_features", []))
        
        # Analyze mood
        mood_results = analyze_playlist_mood(all_audio_features)
        
        # Save analysis
        analysis = await crud_analysis.create_playlist_analysis(
            db,
            user_id,
            playlist_id,
            playlist_name,
            mood_results,
        )
        
        return analysis
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
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get user's analysis history."""
    user_id = UUID(current_user["id"])
    analyses = await crud_analysis.get_user_analyses(db, user_id, limit=limit, offset=offset)
    
    return schemas_analysis.AnalysisHistoryResponse(
        analyses=analyses,
        total=len(analyses),
    )


@router.get("/{analysis_id}", response_model=schemas_analysis.PlaylistAnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific analysis by ID."""
    user_id = UUID(current_user["id"])
    analysis = await crud_analysis.get_playlist_analysis(db, analysis_id)
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    # Verify ownership
    if analysis.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this analysis",
        )
    
    return analysis
