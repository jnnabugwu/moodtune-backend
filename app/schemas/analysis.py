from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime
from uuid import UUID


class PlaylistAnalysisBase(BaseModel):
    playlist_id: str
    playlist_name: str
    mood_results: dict[str, Any]


class PlaylistAnalysisCreate(PlaylistAnalysisBase):
    pass


class PlaylistAnalysisResponse(PlaylistAnalysisBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyzePlaylistRequest(BaseModel):
    playlist_id: str


class AnalysisHistoryResponse(BaseModel):
    analyses: list[PlaylistAnalysisResponse]
    total: int
