from fastapi import APIRouter
from app.api.v1 import spotify, analysis, song_analysis, audio_upload

api_router = APIRouter()

api_router.include_router(spotify.router, prefix="/spotify", tags=["spotify"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(song_analysis.router, prefix="/song", tags=["song-analysis"])
api_router.include_router(audio_upload.router, prefix="/audio-upload", tags=["audio-upload"])