import librosa
import numpy as np
import httpx
import tempfile
import os
from typing import Dict, Optional
import logging
import sentry_sdk
from sentry_sdk import start_transaction, start_span
from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioAnalysisService:
    """
    Analyzes a single song's mood from audio.
    Uses librosa to extract features from Spotify's 30-second preview.
    """

    def __init__(self):
        # Mood mapping (valence-energy model)
        self.mood_map = {
            'happy': {'valence': 0.7, 'energy': 0.7},
            'sad': {'valence': 0.3, 'energy': 0.3},
            'energetic': {'valence': 0.6, 'energy': 0.9},
            'calm': {'valence': 0.5, 'energy': 0.2},
            'angry': {'valence': 0.3, 'energy': 0.9},
        }

    async def download_preview(self, preview_url: str) -> Optional[str]:
        """Download 30-second preview from Spotify"""
        if not preview_url:
            return None

        try:
            sentry_sdk.add_breadcrumb(
                category="download",
                message=f"Downloading preview: {preview_url[:50]}...",
                level="info",
            )
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(preview_url)
                response.raise_for_status()

                # Save to temp file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_file.write(response.content)
                temp_file.close()

                logger.info(f"Downloaded preview: {preview_url[:50]}...")
                sentry_sdk.add_breadcrumb(
                    category="download",
                    message="Preview download completed",
                    level="info",
                )
                return temp_file.name

        except Exception as e:
            logger.error(f"Download failed: {e}")
            sentry_sdk.capture_exception(e)
            return None

    def analyze_audio_file(self, audio_path: str) -> Dict:
        """
        Analyze audio and extract mood features.
        Returns: tempo, energy, valence, danceability, etc.
        """
        with start_transaction(op="audio_analysis", name="analyze_song"):
            try:
                with start_span(op="audio.load", description="Load audio file"):
                    # Load audio (30 seconds)
                    y, sr = librosa.load(audio_path, duration=30)
                    sentry_sdk.set_context(
                        "audio",
                        {
                            "sample_rate": sr,
                            "duration_seconds": len(y) / sr if sr else None,
                        },
                    )

                with start_span(op="audio.tempo", description="Extract tempo"):
                    # 1. Tempo (BPM)
                    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

                with start_span(op="audio.features", description="Extract audio features"):
                    # 2. Energy (loudness)
                    rms = librosa.feature.rms(y=y)
                    energy = float(np.mean(rms))
                    energy_normalized = self._normalize(energy, 0, 0.5)

                    # 3. Brightness (spectral centroid)
                    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
                    brightness = float(np.mean(spectral_centroid))

                    # 4. Chroma (harmony)
                    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
                    chroma_mean = np.mean(chroma, axis=1)

                with start_span(op="audio.calculate", description="Calculate mood metrics"):
                    # 5. Valence (happiness) - estimated from brightness and tempo
                    valence = self._estimate_valence(brightness, chroma_mean, tempo)

                    # 6. Danceability - from tempo and energy
                    danceability = self._estimate_danceability(tempo, energy_normalized)

                    # 7. Loudness
                    loudness = float(librosa.amplitude_to_db(rms).mean())

                features = {
                    "tempo": round(float(tempo), 1),
                    "energy": round(energy_normalized, 2),
                    "valence": round(valence, 2),
                    "danceability": round(danceability, 2),
                    "loudness": round(loudness, 1),
                }
                sentry_sdk.set_context("audio_features", features)
                return features

            except Exception as e:
                logger.error(f"Analysis failed: {e}")
                sentry_sdk.capture_exception(e)
                return self._default_features()

    def analyze_uploaded_audio(self, file_data: bytes, filename: str) -> Dict:
        """
        Analyze audio from uploaded file bytes.
        Writes to a temp file for librosa, then deletes immediately.
        """
        temp_path = None
        with start_transaction(op="audio_analysis", name="analyze_upload"):
            try:
                with start_span(op="audio.tempfile", description="Write temp audio file"):
                    temp_path = self._write_temp_file(file_data, filename)

                with start_span(op="audio.load", description="Load uploaded audio"):
                    y, sr = librosa.load(temp_path, sr=22050, mono=True)
                    if sr is None or sr == 0 or y is None or len(y) == 0:
                        raise ValueError("Failed to decode audio data")
                    duration_seconds = float(len(y) / sr)
                    sentry_sdk.set_context(
                        "audio_upload",
                        {
                            "sample_rate": sr,
                            "duration_seconds": duration_seconds,
                            "filename": filename,
                            "bytes": len(file_data),
                        },
                    )

                with start_span(op="audio.features", description="Extract upload features"):
                    features = self._extract_upload_features(y, sr, duration_seconds)

                return features
            except Exception as e:
                logger.error(f"Upload analysis failed: {e}")
                sentry_sdk.capture_exception(e)
                raise
            finally:
                if temp_path:
                    self.cleanup_temp_file(temp_path)

    def _estimate_valence(self, brightness: float, chroma: np.ndarray, tempo: float) -> float:
        """Estimate happiness from audio features"""
        # Brighter + faster = happier
        brightness_norm = self._normalize(brightness, 1000, 4000)
        tempo_norm = self._normalize(tempo, 60, 180)

        valence = (brightness_norm * 0.6) + (tempo_norm * 0.4)
        return max(0, min(1, valence))

    def _estimate_danceability(self, tempo: float, energy: float) -> float:
        """Estimate danceability from tempo and energy"""
        # Best dance tempo: 90-130 BPM
        optimal_tempo = 110
        tempo_distance = abs(tempo - optimal_tempo)
        tempo_score = max(0, 1 - (tempo_distance / 100))

        danceability = (tempo_score * 0.5) + (energy * 0.5)
        return max(0, min(1, danceability))

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize to 0-1"""
        if max_val == min_val:
            return 0.5
        normalized = (value - min_val) / (max_val - min_val)
        return max(0, min(1, normalized))

    def _extract_upload_features(
        self,
        y: np.ndarray,
        sr: int,
        duration_seconds: float,
    ) -> Dict:
        """Extract mood-relevant features for uploaded audio."""
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        beat_strength = float(np.mean(onset_env) / (np.max(onset_env) + 1e-9))

        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)

        y_harmonic, y_percussive = librosa.effects.hpss(y)
        harm_rms = float(np.mean(librosa.feature.rms(y=y_harmonic)))
        perc_rms = float(np.mean(librosa.feature.rms(y=y_percussive)))
        harmonic_ratio = harm_rms / (harm_rms + perc_rms + 1e-9)

        zero_crossing_rate = float(np.mean(librosa.feature.zero_crossing_rate(y)))

        rms = librosa.feature.rms(y=y)
        rms_energy = float(np.mean(rms))
        dynamic_range = float(np.percentile(rms, 95) - np.percentile(rms, 5))

        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=3)
        mfcc_mean = np.mean(mfcc, axis=1).tolist()

        return {
            "tempo": round(float(tempo), 2),
            "beat_strength": round(beat_strength, 3),
            "spectral_centroid": round(float(np.mean(spectral_centroid)), 2),
            "spectral_rolloff": round(float(np.mean(spectral_rolloff)), 2),
            "spectral_bandwidth": round(float(np.mean(spectral_bandwidth)), 2),
            "harmonic_ratio": round(harmonic_ratio, 3),
            "zero_crossing_rate": round(zero_crossing_rate, 4),
            "rms_energy": round(rms_energy, 4),
            "dynamic_range": round(dynamic_range, 4),
            "mfcc_mean": [round(float(v), 4) for v in mfcc_mean],
            "duration_seconds": round(duration_seconds, 2),
        }

    def _default_upload_features(self) -> Dict:
        """Fallback upload features if analysis fails."""
        return {
            "tempo": 120.0,
            "beat_strength": 0.5,
            "spectral_centroid": 2000.0,
            "spectral_rolloff": 4000.0,
            "spectral_bandwidth": 1500.0,
            "harmonic_ratio": 0.5,
            "zero_crossing_rate": 0.1,
            "rms_energy": 0.1,
            "dynamic_range": 0.1,
            "mfcc_mean": [0.0, 0.0, 0.0],
            "duration_seconds": 0.0,
        }

    def _write_temp_file(self, file_data: bytes, filename: str) -> str:
        """Write bytes to a temporary file in the configured temp directory."""
        os.makedirs(settings.TEMP_AUDIO_DIR, exist_ok=True)
        suffix = os.path.splitext(filename)[1]
        fd, temp_path = tempfile.mkstemp(
            suffix=suffix,
            dir=settings.TEMP_AUDIO_DIR,
        )
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(file_data)
        return temp_path

    def _default_features(self) -> Dict:
        """Fallback if analysis fails"""
        return {
            "tempo": 120.0,
            "energy": 0.5,
            "valence": 0.5,
            "danceability": 0.5,
            "loudness": -10.0,
        }

    def determine_mood(self, features: Dict) -> Dict:
        """
        Determine mood from features.
        Uses simple valence-energy quadrants.
        """
        valence = features['valence']
        energy = features['energy']

        # Mood quadrants
        if valence > 0.6 and energy > 0.6:
            mood = "happy"
        elif valence < 0.4 and energy < 0.4:
            mood = "sad"
        elif valence < 0.4 and energy > 0.6:
            mood = "angry"
        elif energy < 0.4:
            mood = "calm"
        else:
            mood = "energetic"

        # Calculate confidence
        distance_to_mood = self._distance_to_mood(mood, valence, energy)
        confidence = max(0, 1 - (distance_to_mood / 1.5))

        return {
            "primary_mood": mood,
            "confidence": round(confidence, 2),
            "valence": valence,
            "energy": energy,
        }

    def determine_upload_mood(self, features: Dict) -> Dict:
        """
        Determine mood from upload features.
        Maps spectral brightness, tempo, and rms energy to valence/energy.
        """
        brightness = features.get("spectral_centroid", 0.0)
        tempo = features.get("tempo", 120.0)
        rms_energy = features.get("rms_energy", 0.0)

        valence = self._estimate_valence(brightness, np.array([0.0]), tempo)
        energy = self._normalize(rms_energy, 0.0, 0.5)

        mood = self.determine_mood({"valence": valence, "energy": energy})

        return {
            "primary_mood": mood["primary_mood"],
            "confidence": mood["confidence"],
            "mood_scores": {
                "valence": round(valence, 2),
                "energy": round(energy, 2),
                "tempo": round(float(tempo), 2),
                "brightness": round(float(brightness), 2),
            },
            "reasoning": "Derived from tempo, brightness, and energy patterns.",
        }

    def _distance_to_mood(self, mood: str, valence: float, energy: float) -> float:
        """Calculate distance to mood center"""
        target = self.mood_map[mood]
        distance = np.sqrt(
            (target['valence'] - valence) ** 2 +
            (target['energy'] - energy) ** 2
        )
        return distance

    def cleanup_temp_file(self, file_path: str):
        """Delete temp file"""
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


# Singleton instance
audio_analysis_service = AudioAnalysisService()
