from fastapi import APIRouter

from app.core.config import settings
from app.schemas.app_config import AppConfigResponse

router = APIRouter()


@router.get("/config", response_model=AppConfigResponse)
async def get_app_config():
    """Remote flags for the app (unauthenticated). ON_DEVICE_MOOD_ENABLED is
    the kill switch for on-device mood classification."""
    return AppConfigResponse(on_device_mood=settings.ON_DEVICE_MOOD_ENABLED)
