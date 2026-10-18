"""Warm the audio analysis code before the server takes requests.

librosa compiles parts of itself with numba the first time they run. In a
fresh process the first analysis is ~25x slower than the next (12 s vs 0.5 s
on a laptop, over a minute on Railway), so the first user after every deploy
waited for it. Running one short synthetic analysis per code path at startup
moves that cost before the health check passes, and Railway only routes
traffic to a deployment once it is healthy.
"""

import io
import logging
import time
import wave

import numpy as np

from app.services.audio_analysis_service import (
    AudioAnalysisService,
    audio_analysis_service,
)

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 22050


def synthetic_wav(seconds: float = 10.0) -> bytes:
    """A pulsing 220 Hz tone as 16-bit mono WAV: enough rhythm and harmonics
    for beat tracking, HPSS and chroma to run their full code paths."""
    t = np.arange(int(_SAMPLE_RATE * seconds)) / _SAMPLE_RATE
    pulse = (1 + np.sign(np.sin(2 * np.pi * 2 * t))) / 2
    tone = 0.3 * np.sin(2 * np.pi * 220 * t) * pulse
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(_SAMPLE_RATE)
        out.writeframes((tone * 32767).astype(np.int16).tobytes())
    return buffer.getvalue()


def warm_up_audio_analysis(
    service: AudioAnalysisService = audio_analysis_service,
) -> bool:
    """Runs each analysis path once, independently, so one failing path
    still leaves the other warm. Never raises: a failed warm-up only means
    the first real request is slow, so it must not block startup.

    Returns whether every path ran.
    """
    audio = synthetic_wav()
    started = time.perf_counter()
    ok = True

    # Uploads and catalog tracks; failures raise.
    try:
        service.analyze_uploaded_audio(audio, "warmup.wav")
    except Exception:
        logger.exception("Upload analysis warm-up failed; first request will be slow")
        ok = False

    # Spotify songs (adds chroma). This path logs its own failures and
    # returns fallback features instead of raising, so check the result.
    try:
        features = service.analyze_audio_bytes(audio, "warmup.wav")
        if features == service._default_features():
            raise RuntimeError("song analysis returned fallback features")
    except Exception:
        logger.exception("Song analysis warm-up failed; first request will be slow")
        ok = False

    if ok:
        logger.info("Audio analysis warmed up in %.1fs", time.perf_counter() - started)
    return ok
