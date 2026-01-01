from typing import List, Dict, Any


def analyze_playlist_mood(audio_features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze mood of a playlist based on audio features.
    
    Args:
        audio_features: List of audio feature objects from Spotify API
        
    Returns:
        dict: Mood analysis results including averages and mood classification
    """
    # Filter out None values (some tracks may not have features)
    valid_features = [f for f in audio_features if f is not None]
    
    if not valid_features:
        return {
            "error": "No valid audio features found",
            "track_count": 0,
        }
    
    # Calculate averages
    total_tracks = len(valid_features)
    avg_valence = sum(f.get("valence", 0) for f in valid_features) / total_tracks
    avg_energy = sum(f.get("energy", 0) for f in valid_features) / total_tracks
    avg_danceability = sum(f.get("danceability", 0) for f in valid_features) / total_tracks
    avg_tempo = sum(f.get("tempo", 0) for f in valid_features) / total_tracks
    avg_acousticness = sum(f.get("acousticness", 0) for f in valid_features) / total_tracks
    avg_instrumentalness = sum(f.get("instrumentalness", 0) for f in valid_features) / total_tracks
    
    # Determine primary mood based on valence and energy
    # Valence: 0 = sad/depressing, 1 = happy/cheerful
    # Energy: 0 = calm/peaceful, 1 = energetic/intense
    
    if avg_valence > 0.6 and avg_energy > 0.6:
        primary_mood = "Happy & Energetic"
        mood_category = "upbeat"
    elif avg_valence > 0.6 and avg_energy <= 0.6:
        primary_mood = "Happy & Calm"
        mood_category = "peaceful"
    elif avg_valence <= 0.6 and avg_energy > 0.6:
        primary_mood = "Intense & Dark"
        mood_category = "intense"
    else:
        primary_mood = "Calm & Melancholic"
        mood_category = "calm"
    
    # Additional mood descriptors
    mood_descriptors = []
    if avg_danceability > 0.7:
        mood_descriptors.append("danceable")
    if avg_acousticness > 0.5:
        mood_descriptors.append("acoustic")
    if avg_instrumentalness > 0.5:
        mood_descriptors.append("instrumental")
    if avg_tempo > 120:
        mood_descriptors.append("fast-paced")
    elif avg_tempo < 90:
        mood_descriptors.append("slow-paced")
    
    return {
        "primary_mood": primary_mood,
        "mood_category": mood_category,
        "mood_descriptors": mood_descriptors,
        "averages": {
            "valence": round(avg_valence, 3),
            "energy": round(avg_energy, 3),
            "danceability": round(avg_danceability, 3),
            "tempo": round(avg_tempo, 2),
            "acousticness": round(avg_acousticness, 3),
            "instrumentalness": round(avg_instrumentalness, 3),
        },
        "track_count": total_tracks,
        "raw_features": valid_features,  # Include raw data for detailed analysis
    }
