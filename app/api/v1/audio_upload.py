from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
import os
import time
from typing import Optional
from app.core.config import settings
from app.schemas.audio_analysis import AudioFeatures, MoodFromAudio, AudioAnalysisResponse
from app.services.audio_analysis_service import audio_analysis_service


router = APIRouter()


@router.post("/analyze", response_model=AudioAnalysisResponse)
async def analyze_uploaded_audio(
    audio_file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    artist: Optional[str] = Form(default=None),
    album: Optional[str] = Form(default=None),
):
    """
    Analyze user-uploaded audio (guest endpoint).
    Processes the file in-memory and deletes temp data immediately.
    """
    if not audio_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is required",
        )

    extension = os.path.splitext(audio_file.filename)[1].lstrip(".").lower()
    if extension not in settings.ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {extension}",
        )

    file_data = await audio_file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    start_time = time.time()
    try:
        features = audio_analysis_service.analyze_uploaded_audio(
            file_data=file_data,
            filename=audio_file.filename,
        )
        mood_summary = audio_analysis_service.determine_upload_mood(features)
        processing_time = time.time() - start_time
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio analysis failed: {str(e)}",
        )

    audio_features = AudioFeatures(**features)
    mood = MoodFromAudio(
        primary_mood=mood_summary["primary_mood"],
        mood_scores=mood_summary["mood_scores"],
        confidence=mood_summary["confidence"],
        reasoning=mood_summary["reasoning"],
        audio_features=audio_features,
    )

    return AudioAnalysisResponse(
        user_id=None,
        filename=audio_file.filename,
        file_size_bytes=len(file_data),
        duration_seconds=audio_features.duration_seconds,
        title=title,
        artist=artist,
        album=album,
        mood=mood,
        processing_time_seconds=round(processing_time, 2),
    )
