import httpx
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from urllib.parse import urlencode
from app.core.config import settings


def generate_authorize_url(state: str) -> str:
    """
    Generate Spotify OAuth authorization URL.
    
    Args:
        state: CSRF protection state parameter
        
    Returns:
        str: Spotify authorization URL
    """
    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": "user-read-private user-read-email playlist-read-private playlist-read-collaborative",
        "state": state,
    }
    
    return f"https://accounts.spotify.com/authorize?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> Dict[str, any]:
    """
    Exchange authorization code for access and refresh tokens.
    
    Args:
        code: Authorization code from Spotify callback
        
    Returns:
        dict: Contains access_token, refresh_token, expires_in, token_type
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
            },
            auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> Dict[str, any]:
    """
    Refresh an expired access token using refresh token.
    
    Args:
        refresh_token: The refresh token
        
    Returns:
        dict: Contains access_token, expires_in, token_type
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def get_spotify_user_id(access_token: str) -> str:
    """
    Get Spotify user ID from access token.
    
    Args:
        access_token: Valid Spotify access token
        
    Returns:
        str: Spotify user ID
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()
        return data["id"]




