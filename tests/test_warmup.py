import io
import wave

from fastapi.testclient import TestClient

import app.main as main
from app.core.config import settings
from app.services.warmup import synthetic_wav, warm_up_audio_analysis


_FALLBACK = {"tempo": 0.0}


class _RecordingService:
    """Records calls; `upload_error` / `song_error` make that path raise and
    `song_fallback` makes the song path return its fallback features."""

    def __init__(self, upload_error=None, song_error=None, song_fallback=False):
        self.calls = []
        self.upload_error = upload_error
        self.song_error = song_error
        self.song_fallback = song_fallback

    def analyze_uploaded_audio(self, data, filename):
        self.calls.append(("upload", filename))
        if self.upload_error:
            raise self.upload_error

    def analyze_audio_bytes(self, data, filename):
        self.calls.append(("song", filename))
        if self.song_error:
            raise self.song_error
        return _FALLBACK if self.song_fallback else {"tempo": 120.0}

    def _default_features(self):
        return _FALLBACK


def test_synthetic_wav_is_ten_seconds_of_mono_16_bit_audio():
    with wave.open(io.BytesIO(synthetic_wav()), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getnframes() == audio.getframerate() * 10


def test_warm_up_runs_upload_and_song_paths():
    service = _RecordingService()

    assert warm_up_audio_analysis(service) is True
    assert service.calls == [("upload", "warmup.wav"), ("song", "warmup.wav")]


def test_upload_failure_still_warms_the_song_path(caplog):
    service = _RecordingService(upload_error=RuntimeError("no codec"))

    assert warm_up_audio_analysis(service) is False
    assert service.calls == [("upload", "warmup.wav"), ("song", "warmup.wav")]
    assert "Upload analysis warm-up failed" in caplog.text


def test_song_failure_is_logged_not_raised(caplog):
    service = _RecordingService(song_error=RuntimeError("boom"))

    assert warm_up_audio_analysis(service) is False
    assert "Song analysis warm-up failed" in caplog.text


def test_song_fallback_features_count_as_a_failure(caplog):
    service = _RecordingService(song_fallback=True)

    assert warm_up_audio_analysis(service) is False
    assert "fallback features" in caplog.text


def test_warm_up_runs_the_real_analysis():
    # Compiles librosa's numba code (~10 s). True means both paths ran and
    # the song path produced real features, not its fallback.
    assert warm_up_audio_analysis() is True


def test_startup_warms_up_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "warm_up_audio_analysis", lambda: calls.append(1))
    monkeypatch.setattr(settings, "WARM_UP_ON_STARTUP", True)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200

    assert calls == [1]


def test_startup_skips_warm_up_when_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "warm_up_audio_analysis", lambda: calls.append(1))
    monkeypatch.setattr(settings, "WARM_UP_ON_STARTUP", False)

    with TestClient(main.app):
        pass

    assert calls == []
