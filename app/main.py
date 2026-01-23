from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from app.core.config import settings
from app.api.v1.api import api_router

# Initialize Sentry before creating the FastAPI app
if settings.SENTRY_ENABLE and settings.SENTRY_DSN_BACKEND:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN_BACKEND,
        environment=settings.ENVIRONMENT,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=None, event_level=None),
        ],
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )

app = FastAPI(
    title="MoodTune API",
    description="A music mood analysis and playlist generation API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to MoodTune API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 


if settings.ENVIRONMENT == "development":
    @app.get("/sentry-debug")
    async def sentry_debug():
        """Trigger an error to verify Sentry reporting in development."""
        _ = 1 / 0