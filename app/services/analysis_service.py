"""
Playlist mood analysis service.

Analyzes Spotify audio features to determine playlist mood characteristics.
"""
from typing import List, Dict, Any, Optional


# ============================================================================
# Mood Classification Thresholds
# ============================================================================

THRESHOLDS = {
    "valence": {
        "happy": 0.6,    # >= 0.6 considered happy
        "sad": 0.4,      # < 0.4 considered sad
    },
    "energy": {
        "energetic": 0.6,  # >= 0.6 considered energetic
        "calm": 0.4,       # < 0.4 considered calm
    },
    "danceability": {
        "danceable": 0.6,  # >= 0.6 considered danceable
    },
}


# ============================================================================
# Individual Track Classification
# ============================================================================

def classify_track_mood(valence: float, energy: float) -> str:
    """
    Classify mood for a single track based on valence and energy.
    
    Args:
        valence: 0.0 (sad) to 1.0 (happy)
        energy: 0.0 (calm) to 1.0 (energetic)
    
    Returns:
        Mood classification string
    """
    if valence >= 0.6 and energy >= 0.6:
        return "Happy & Energetic"
    elif valence >= 0.6 and energy < 0.6:
        return "Happy & Calm"
    elif valence < 0.4 and energy >= 0.6:
        return "Sad & Energetic"
    elif valence < 0.4 and energy < 0.6:
        return "Sad & Calm"
    else:
        return "Neutral"


# ============================================================================
# Mood Distribution Calculation
# ============================================================================

def calculate_mood_distribution(audio_features: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate percentage distribution of moods across all tracks.
    
    Args:
        audio_features: List of audio feature objects
        
    Returns:
        Dict with mood percentages (happy, sad, energetic, calm, danceable)
    """
    total = len(audio_features)
    if total == 0:
        return {"happy": 0, "sad": 0, "energetic": 0, "calm": 0, "danceable": 0}
    
    happy_count = sum(1 for f in audio_features if f.get("valence", 0) >= THRESHOLDS["valence"]["happy"])
    sad_count = sum(1 for f in audio_features if f.get("valence", 0) < THRESHOLDS["valence"]["sad"])
    energetic_count = sum(1 for f in audio_features if f.get("energy", 0) >= THRESHOLDS["energy"]["energetic"])
    calm_count = sum(1 for f in audio_features if f.get("energy", 0) < THRESHOLDS["energy"]["calm"])
    danceable_count = sum(1 for f in audio_features if f.get("danceability", 0) >= THRESHOLDS["danceability"]["danceable"])
    
    return {
        "happy": round((happy_count / total) * 100, 1),
        "sad": round((sad_count / total) * 100, 1),
        "energetic": round((energetic_count / total) * 100, 1),
        "calm": round((calm_count / total) * 100, 1),
        "danceable": round((danceable_count / total) * 100, 1),
    }


# ============================================================================
# Confidence Score Calculation
# ============================================================================

def calculate_confidence(avg_valence: float, avg_energy: float) -> float:
    """
    Calculate confidence in mood classification.
    
    Higher confidence when averages are further from the center (0.5, 0.5).
    Lower confidence when averages are near the center (mixed/neutral mood).
    
    Args:
        avg_valence: Average valence (0-1)
        avg_energy: Average energy (0-1)
        
    Returns:
        Confidence score (0-100)
    """
    # Calculate distance from center point (0.5, 0.5)
    # Maximum distance is ~0.707 (corner to center)
    center_valence = 0.5
    center_energy = 0.5
    
    distance = ((avg_valence - center_valence) ** 2 + (avg_energy - center_energy) ** 2) ** 0.5
    max_distance = 0.707  # sqrt(0.5^2 + 0.5^2)
    
    # Normalize to 0-100 scale
    # Minimum confidence of 30% even for centered playlists
    confidence = 30 + (distance / max_distance) * 70
    
    return round(min(100, confidence), 1)


# ============================================================================
# Top Tracks Selection
# ============================================================================

def select_top_tracks(
    audio_features: List[Dict[str, Any]],
    track_metadata: Dict[str, Dict[str, Any]],
    count: int = 5,
) -> List[Dict[str, Any]]:
    """
    Select top representative tracks from the playlist.
    
    Initial simple implementation - selects tracks with highest combined
    valence and energy scores (most "mood-forward" tracks).
    
    NOTE: This logic is intentionally simple for now. Will be refined later.
    
    Args:
        audio_features: List of audio feature objects
        track_metadata: Dict mapping track_id to {name, artists}
        count: Number of top tracks to return
        
    Returns:
        List of TrackAnalysis-compatible dicts
    """
    # Score each track by how "interesting" it is (distance from neutral)
    scored_tracks = []
    for features in audio_features:
        track_id = features.get("id")
        if not track_id:
            continue
            
        valence = features.get("valence", 0.5)
        energy = features.get("energy", 0.5)
        danceability = features.get("danceability", 0.5)
        
        # Simple scoring: prefer tracks far from neutral
        distance_from_center = ((valence - 0.5) ** 2 + (energy - 0.5) ** 2) ** 0.5
        
        metadata = track_metadata.get(track_id, {})
        
        scored_tracks.append({
            "track_id": track_id,
            "track_name": metadata.get("name", "Unknown Track"),
            "artists": metadata.get("artists", []),
            "valence": round(valence, 3),
            "energy": round(energy, 3),
            "danceability": round(danceability, 3),
            "mood_label": classify_track_mood(valence, energy),
            "_score": distance_from_center,
        })
    
    # Sort by score (highest first) and take top N
    scored_tracks.sort(key=lambda x: x["_score"], reverse=True)
    
    # Remove the internal score field before returning
    top_tracks = []
    for track in scored_tracks[:count]:
        track_copy = {k: v for k, v in track.items() if k != "_score"}
        top_tracks.append(track_copy)
    
    return top_tracks


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_playlist_mood(
    audio_features: List[Dict[str, Any]],
    track_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Analyze mood of a playlist based on audio features.
    
    Args:
        audio_features: List of audio feature objects from Spotify API
        track_metadata: Optional dict mapping track_id to {name, artists}
        
    Returns:
        dict: Complete mood analysis results matching MoodResult schema
    """
    # Filter out None values (some tracks may not have features)
    valid_features = [f for f in audio_features if f is not None]
    
    if not valid_features:
        return {
            "primary_mood": "Unknown",
            "mood_category": "unknown",
            "mood_descriptors": [],
            "confidence": 0,
            "averages": {
                "valence": 0,
                "energy": 0,
                "danceability": 0,
                "tempo": 0,
                "acousticness": 0,
                "instrumentalness": 0,
            },
            "mood_distribution": {
                "happy": 0,
                "sad": 0,
                "energetic": 0,
                "calm": 0,
                "danceable": 0,
            },
            "top_tracks": [],
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
    
    # Calculate mood distribution
    mood_distribution = calculate_mood_distribution(valid_features)
    
    # Calculate confidence score
    confidence = calculate_confidence(avg_valence, avg_energy)
    
    # Select top representative tracks
    top_tracks = []
    if track_metadata:
        top_tracks = select_top_tracks(valid_features, track_metadata, count=5)
    
    return {
        "primary_mood": primary_mood,
        "mood_category": mood_category,
        "mood_descriptors": mood_descriptors,
        "confidence": confidence,
        "averages": {
            "valence": round(avg_valence, 3),
            "energy": round(avg_energy, 3),
            "danceability": round(avg_danceability, 3),
            "tempo": round(avg_tempo, 2),
            "acousticness": round(avg_acousticness, 3),
            "instrumentalness": round(avg_instrumentalness, 3),
        },
        "mood_distribution": mood_distribution,
        "top_tracks": top_tracks,
        "track_count": total_tracks,
    }
