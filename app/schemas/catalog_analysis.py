from pydantic import BaseModel


class CatalogAnalyzeRequest(BaseModel):
    audio_url: str          # Jamendo audiodownload stream URL
    track_id: str           # Jamendo track ID (used for temp filename)
    track_name: str
    artist_name: str
    jamendo_page_url: str = ""  # Attribution link — passed through to response
    # Apps that save the finished result themselves (POST /song/history, with
    # both engines' moods) send False; older apps rely on the default.
    save_to_history: bool = True
