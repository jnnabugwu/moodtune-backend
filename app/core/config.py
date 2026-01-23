import os
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE_MAP = {
    "development": "dev.env",
    "staging": "staging.env",
    "production": ".env",
}


def _select_env_file() -> str:
    """
    Pick an environment file based on ENVIRONMENT; defaults to dev.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    return ENV_FILE_MAP.get(env, ".env")


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MoodTune"
    APP_NAME: str = "MoodTune"
    VERSION: str = "1.0.0"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Authentication
    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None  # Anon key for frontend
    SUPABASE_SERVICE_KEY: Optional[str] = None  # Service role key for backend
    
    # Spotify API
    SPOTIFY_CLIENT_ID: Optional[str] = None
    SPOTIFY_CLIENT_SECRET: Optional[str] = None
    SPOTIFY_REDIRECT_URI: Optional[str] = None
    SPOTIFY_SCOPES: str = (
        "user-read-private user-read-email playlist-read-private "
        "playlist-read-collaborative"
    )
    # Optional deep link / frontend URL to redirect after callback
    SPOTIFY_APP_REDIRECT_URI: Optional[str] = None
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Sentry
    SENTRY_DSN_BACKEND: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 1.0
    SENTRY_ENABLE: bool = True

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=_select_env_file()
    )


settings = Settings() 