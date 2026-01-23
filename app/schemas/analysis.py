from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


# ============================================================================
# Track Analysis Models
# ============================================================================

class TrackAnalysis(BaseModel):
    """Individual track with mood analysis."""
    track_id: str
    track_name: str
    artists: list[str]
    valence: float
    energy: float
    danceability: float
    mood_label: str


# ============================================================================
# Mood Analysis Models
# ============================================================================

class MoodDistribution(BaseModel):
    """Percentage distribution of moods across playlist tracks."""
    happy: float       # % of tracks with valence >= 0.6
    sad: float         # % of tracks with valence < 0.4
    energetic: float   # % of tracks with energy >= 0.6
    calm: float        # % of tracks with energy < 0.4
    danceable: float   # % of tracks with danceability >= 0.6


class AudioFeaturesSummary(BaseModel):
    """Average audio features across all analyzed tracks."""
    valence: float
    energy: float
    danceability: float
    tempo: float
    acousticness: float
    instrumentalness: float


class MoodResult(BaseModel):
    """Complete mood analysis result."""
    primary_mood: str
    mood_category: str
    mood_descriptors: list[str]
    confidence: float
    averages: AudioFeaturesSummary
    mood_distribution: MoodDistribution
    top_tracks: list[TrackAnalysis]
    track_count: int


# ============================================================================
# API Request/Response Models
# ============================================================================

class PlaylistAnalysisBase(BaseModel):
    playlist_id: str
    playlist_name: str


class PlaylistAnalysisResponse(PlaylistAnalysisBase):
    """Response model for playlist analysis."""
    id: UUID
    user_id: UUID
    mood_results: MoodResult
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyzePlaylistRequest(BaseModel):
    playlist_id: str


class AnalysisHistoryResponse(BaseModel):
    analyses: list[PlaylistAnalysisResponse]
    total: int
