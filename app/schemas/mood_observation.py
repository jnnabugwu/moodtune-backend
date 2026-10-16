"""Schemas for mood observations (backend vs on-device mood + user feedback).

PRIVACY: these models deliberately have no filename/title/artist fields.
Unknown request fields are ignored (pydantic's default), so they are never
stored even if a client sends them.
"""
from typing import Annotated, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

MAX_TAGS = 10
MAX_TAG_LENGTH = 40
MAX_PROBABILITIES = 10
MAX_ERROR_LENGTH = 500
MAX_STRING_LENGTH = 100

ObservationSource = Literal["upload", "catalog"]
DisplayedSource = Literal["on_device", "backend"]
# Classifier labels (determine_mood); the on-device model and the results
# screen's displayed_mood use the same vocabulary. Mirrored by the CHECK
# constraints in db/mood_observations.sql.
Mood = Literal["happy", "energetic", "calm", "angry", "sad"]
# The app's 4 display buckets, used only for the user's own feedback.
UserMood = Literal["upbeat", "serene", "charged", "reflective"]

ShortStr = Annotated[str, StringConstraints(max_length=MAX_STRING_LENGTH)]
Tag = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TAG_LENGTH),
]
Probability = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


class MoodObservationCreate(BaseModel):
    """Body of POST /mood-observations (upsert by client-generated id)."""

    id: UUID
    source: ObservationSource
    analysis_id: Optional[ShortStr] = None
    backend_mood: Mood
    on_device_mood: Optional[Mood] = None
    on_device_tags: List[Tag] = Field(default_factory=list, max_length=MAX_TAGS)
    on_device_probabilities: Optional[Dict[Mood, Probability]] = Field(
        default=None, max_length=MAX_PROBABILITIES
    )
    on_device_latency_ms: Optional[int] = Field(default=None, ge=0, le=600_000)
    on_device_error: Optional[str] = Field(default=None, max_length=MAX_ERROR_LENGTH)
    displayed_mood: Mood
    displayed_source: DisplayedSource
    platform: Optional[ShortStr] = None
    os_version: Optional[ShortStr] = None
    device_model: Optional[ShortStr] = None
    app_version: Optional[ShortStr] = None

    @model_validator(mode="after")
    def _on_device_display_needs_on_device_mood(self) -> "MoodObservationCreate":
        if self.displayed_source == "on_device" and not self.on_device_mood:
            raise ValueError(
                "on_device_mood is required when displayed_source is 'on_device'"
            )
        return self

    def to_row(self) -> dict:
        """Columns to upsert. Feedback columns are never touched here."""
        return self.model_dump(mode="json")


class MoodObservationCreated(BaseModel):
    id: UUID


class MoodFeedbackUpdate(BaseModel):
    """Body of PATCH /mood-observations/{id}/feedback."""

    agrees: bool
    user_mood: Optional[UserMood] = None


class MoodFeedbackResult(BaseModel):
    id: UUID
    agrees: bool
    user_mood: Optional[UserMood] = None
