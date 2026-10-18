"""Schemas for saving a finished upload/catalog result to the user's history.

The app saves the row itself once the result is final, so it can record both
engines: the backend's rule-based mood and the on-device (YAMNet) mood, plus
which one the results screen showed. No audio is sent.
"""
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.mood_observation import DisplayedSource, Mood, ObservationSource

MAX_TITLE_LENGTH = 200
MAX_TRACK_ID_LENGTH = 100

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH)
]
Artist = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_TITLE_LENGTH)]


class ResultHistoryCreate(BaseModel):
    """Body of POST /song/history."""

    source: ObservationSource
    title: Title
    # True when the app made `title` from the upload's filename because the
    # user typed none. Shares leave such titles out. Older apps omit it.
    title_from_filename: bool = False
    artist: Optional[Artist] = None
    track_id: Optional[Annotated[str, StringConstraints(max_length=MAX_TRACK_ID_LENGTH)]] = None
    displayed_mood: Mood
    displayed_source: DisplayedSource
    backend_mood: Mood
    on_device_mood: Optional[Mood] = None
    # Only the backend's confidence is meaningful; on-device probabilities
    # are overconfident until recalibrated (ROADMAP OD-5).
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    observation_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _displayed_mood_matches_its_source(self) -> "ResultHistoryCreate":
        shown = self.on_device_mood if self.displayed_source == "on_device" else self.backend_mood
        if self.displayed_mood != shown:
            raise ValueError(
                f"displayed_mood must equal the {self.displayed_source} mood"
            )
        return self

    def to_mood_results(self) -> dict:
        """`primary_mood` and `confidence` keep the shape older apps read."""
        return {
            "primary_mood": self.displayed_mood,
            "confidence": self.confidence,
            "source": self.source,
            "displayed_source": self.displayed_source,
            "backend_mood": self.backend_mood,
            "on_device_mood": self.on_device_mood,
            "observation_id": str(self.observation_id) if self.observation_id else None,
            "title_from_filename": self.title_from_filename,
        }


class ResultHistoryCreated(BaseModel):
    id: str
