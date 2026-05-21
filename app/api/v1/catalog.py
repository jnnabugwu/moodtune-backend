import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.audio_analysis import AudioAnalysisResponse, AudioFeatures, MoodFromAudio
from app.schemas.catalog_analysis import CatalogAnalyzeRequest
from app.services.audio_analysis_service import audio_analysis_service

router = APIRouter()


@router.post("/analyze", response_model=AudioAnalysisResponse)
async def analyze_catalog_track(body: CatalogAnalyzeRequest):
    """
    Unauthenticated endpoint — downloads a Jamendo stream URL server-side
    and runs it through the same librosa pipeline as /audio-upload/analyze.
    """
    # 1. Download audio from Jamendo
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(body.audio_url)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch audio: {e}")

    file_data = resp.content
    filename = f"{body.track_id}.mp3"

    # 2. Validate size
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Track exceeds size limit of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # 3. Run rich analysis pipeline (same as /audio-upload/analyze)
    start = time.time()
    try:
        features = audio_analysis_service.analyze_uploaded_audio(file_data, filename)
        mood_summary = audio_analysis_service.determine_upload_mood(features)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")
    processing_time = time.time() - start

    # 4. Build and return response
    audio_features = AudioFeatures(**features)
    mood = MoodFromAudio(
        primary_mood=mood_summary["primary_mood"],
        mood_scores=mood_summary["mood_scores"],
        confidence=mood_summary["confidence"],
        reasoning=mood_summary["reasoning"],
        audio_features=audio_features,
        descriptors=mood_summary.get("descriptors", []),
    )

    return AudioAnalysisResponse(
        id=uuid.uuid4(),
        user_id=None,
        filename=body.track_name,
        file_size_bytes=len(file_data),
        duration_seconds=audio_features.duration_seconds,
        title=body.track_name,
        artist=body.artist_name,
        mood=mood,
        analysis_method="catalog_stream",
        processed_at=datetime.now(timezone.utc),
        processing_time_seconds=round(processing_time, 2),
        jamendo_track_url=body.jamendo_page_url or None,
    )
