"""Audio decoding shared by the comparison and the tag listening sheet."""

from pathlib import Path

import librosa
import numpy as np

from common import SAMPLE_RATE, WINDOW_POSITIONS, WINDOW_SECONDS


def load_windows_with_starts(path: Path) -> tuple[list[np.ndarray], list[float]]:
    """Decodes to mono 48 kHz and cuts 10 s windows at WINDOW_POSITIONS.

    Returns the windows and where each starts (seconds into the track).
    This decode + resample is the part that needs native code on a phone
    (AVAudioConverter / MediaCodec); librosa hides it here.
    """
    audio, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    size = SAMPLE_RATE * WINDOW_SECONDS
    if len(audio) <= size:
        return [audio], [0.0]  # models repeat-pad or zero-pad short clips
    windows, starts = [], []
    for position in WINDOW_POSITIONS:
        start = int(position * len(audio)) - size // 2
        start = min(max(start, 0), len(audio) - size)
        windows.append(audio[start : start + size])
        starts.append(start / SAMPLE_RATE)
    return windows, starts


def load_windows(path: Path) -> list[np.ndarray]:
    return load_windows_with_starts(path)[0]
