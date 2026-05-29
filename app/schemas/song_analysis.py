from pydantic import BaseModel
from typing import Optional, List


class PlaylistTrack(BaseModel):
    """Track information from a playlist."""
    id: str
    name: str
    artists: List[str]
    preview_url: Optional[str] = None
    image_url: Optional[str] = None
    duration_ms: Optional[int] = None


class PlaylistTracksResponse(BaseModel):
    """Response containing tracks from a playlist."""
    tracks: List[PlaylistTrack]
    total: int


class SongAnalysisRequest(BaseModel):
    """Metadata for song analysis (audio is provided via file upload)."""
    track_name: Optional[str] = None
    artist_name: Optional[str] = None
    track_id: Optional[str] = None


class AudioFeatures(BaseModel):
    """Audio features extracted from the song."""
    tempo: float
    energy: float
    valence: float
    danceability: float
    loudness: float


class MoodResult(BaseModel):
    """Mood classification result."""
    primary_mood: str
    confidence: float
    valence: float
    energy: float


class SongAnalysisResponse(BaseModel):
    """Response with song mood analysis."""
    track_name: str
    artist_name: str
    track_id: Optional[str] = None
    mood: MoodResult
    features: AudioFeatures
    success: bool
    message: str = ""


class SongAnalysisHistoryItem(BaseModel):
    """A single song analysis history row."""
    id: str
    user_id: str
    track_id: Optional[str] = None
    track_name: str
    artist_name: str
    mood_results: dict
    created_at: str


class SongAnalysisHistoryResponse(BaseModel):
    """Response for song analysis history."""
    analyses: list[SongAnalysisHistoryItem]
    total: int
