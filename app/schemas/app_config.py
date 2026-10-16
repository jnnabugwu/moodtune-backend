from pydantic import BaseModel


class AppConfigResponse(BaseModel):
    """Remote flags the app reads at startup (GET /config)."""

    # Kill switch for on-device (YAMNet) mood classification.
    on_device_mood: bool
