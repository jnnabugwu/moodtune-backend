from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
import uuid


class AudioUploadRequest(BaseModel):
    """Metadata sent with audio file."""

    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None


class AudioFeatures(BaseModel):
    """Raw audio features extracted by librosa."""

    tempo: float = Field(description="Beats per minute")
    beat_strength: float = Field(ge=0.0, le=1.0, description="Beat clarity")

    spectral_centroid: float = Field(description="Brightness")
    spectral_rolloff: float = Field(description="High-frequency content")
    spectral_bandwidth: float = Field(description="Frequency spread")

    harmonic_ratio: float = Field(ge=0.0, le=1.0, description="Harmony vs noise")
    zero_crossing_rate: float = Field(description="Percussiveness indicator")

    rms_energy: float = Field(description="Overall loudness")
    dynamic_range: float = Field(description="Variation in loudness")

    mfcc_mean: List[float] = Field(description="Timbre characteristics")
    duration_seconds: float


class MoodFromAudio(BaseModel):
    """Mood inferred from audio features."""

    primary_mood: str
    mood_scores: Dict[str, float] = Field(description="Valence, energy, etc.")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this mood was chosen")
    audio_features: AudioFeatures


class AudioAnalysisResponse(BaseModel):
    """Complete analysis result."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: Optional[str] = None
    filename: str
    file_size_bytes: int
    duration_seconds: float

    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None

    mood: MoodFromAudio
    analysis_method: str = "direct_audio"
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_seconds: float

    class Config:
        from_attributes = True
