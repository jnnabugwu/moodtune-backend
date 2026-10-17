import io
import wave

from fastapi.testclient import TestClient

import app.main as main
from app.core.config import settings
from app.services.warmup import synthetic_wav, warm_up_audio_analysis


class _RecordingService:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def analyze_uploaded_audio(self, data, filename):
        self.calls.append(("upload", filename))
        if self.error:
            raise self.error

    def analyze_audio_bytes(self, data, filename):
        self.calls.append(("song", filename))


def test_synthetic_wav_is_ten_seconds_of_mono_16_bit_audio():
    with wave.open(io.BytesIO(synthetic_wav()), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getnframes() == audio.getframerate() * 10


def test_warm_up_runs_upload_and_song_paths():
    service = _RecordingService()

    assert warm_up_audio_analysis(service) is True
    assert service.calls == [("upload", "warmup.wav"), ("song", "warmup.wav")]


def test_warm_up_failure_is_logged_not_raised(caplog):
    service = _RecordingService(error=RuntimeError("no codec"))

    assert warm_up_audio_analysis(service) is False
    assert "warm-up failed" in caplog.text


def test_warm_up_runs_the_real_analysis():
    # Compiles librosa's numba code (~10 s); proves the synthetic clip
    # exercises the production paths without falling over.
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
