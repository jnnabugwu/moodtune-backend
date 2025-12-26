from fastapi import APIRouter
from app.api.v1 import spotify, analysis

api_router = APIRouter()

api_router.include_router(spotify.router, prefix="/spotify", tags=["spotify"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
