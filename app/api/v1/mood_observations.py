from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import optional_get_current_user
from app.crud import mood_observation as crud_mood_observation
from app.schemas.mood_observation import (
    MoodFeedbackResult,
    MoodFeedbackUpdate,
    MoodObservationCreate,
    MoodObservationCreated,
)

router = APIRouter()


@router.post(
    "",
    response_model=MoodObservationCreated,
    status_code=status.HTTP_201_CREATED,
)
async def record_mood_observation(
    body: MoodObservationCreate,
    current_user: Optional[dict] = Depends(optional_get_current_user),
):
    """
    Record the backend vs on-device mood for one viewed analysis (guest
    endpoint). Upserts by the client-generated id, so retries are safe.
    Signed-in callers are attributed via their token.
    """
    user_id = current_user["id"] if current_user else None
    try:
        await crud_mood_observation.upsert_mood_observation(
            body.to_row(), user_id=user_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not record mood observation: {str(e)}",
        )
    return MoodObservationCreated(id=body.id)


@router.patch("/{observation_id}/feedback", response_model=MoodFeedbackResult)
async def record_mood_feedback(observation_id: UUID, body: MoodFeedbackUpdate):
    """Record the user's "Does this feel right?" answer (guest endpoint)."""
    try:
        row = await crud_mood_observation.update_mood_feedback(
            observation_id, agrees=body.agrees, user_mood=body.user_mood
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not record feedback: {str(e)}",
        )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mood observation not found",
        )
    return MoodFeedbackResult(
        id=observation_id, agrees=body.agrees, user_mood=body.user_mood
    )
