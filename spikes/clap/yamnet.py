"""YAMNet via TFLite: the same 4 MB file and runtime you'd ship on a phone.

YAMNet is a small CNN (MobileNet v1) trained on AudioSet's 521 sound classes.
Unlike CLAP it's a closed label set, but that set happens to include music
moods ("Happy music", "Sad music", ...) plus instruments and vocals.

The .tflite takes raw 16 kHz audio and computes its own spectrogram inside
the graph, so on a device there's no mel front-end to port: only decode,
resample to 16 kHz, and slice into 0.975 s frames.
"""

import csv
import time

import librosa
import numpy as np
from ai_edge_litert.interpreter import Interpreter

from common import ROOT, SAMPLE_RATE, YAMNET_MOOD_CLASSES

MODEL_PATH = ROOT / "models" / "yamnet.tflite"
CLASS_MAP_PATH = ROOT / "models" / "yamnet_class_map.csv"

YAMNET_SR = 16_000
FRAME = 15_600  # 0.975 s: the model's fixed input size
HOP = 7_680  # 0.48 s: the hop YAMNet itself uses when given a long clip

# Too generic to say anything about a track; skipped in the descriptive tags.
GENERIC_CLASSES = {"Music", "Musical instrument", "Speech", "Silence"}


class YamNet:
    def __init__(self) -> None:
        self.interpreter = Interpreter(model_path=str(MODEL_PATH))
        self.interpreter.allocate_tensors()
        self._input = self.interpreter.get_input_details()[0]["index"]
        self._output = self.interpreter.get_output_details()[0]["index"]
        with CLASS_MAP_PATH.open() as f:
            self.class_names = [row["display_name"] for row in csv.DictReader(f)]
        self.mood_index = {
            self.class_names.index(name): label
            for name, label in YAMNET_MOOD_CLASSES.items()
        }

    def frame_scores(
        self, windows_48k: list[np.ndarray]
    ) -> tuple[list[np.ndarray], float]:
        """Per-frame class scores for each window, (n_frames, 521) each, + ms per frame.

        Scores are independent sigmoids (AudioSet is multi-label), so they
        don't sum to 1: a track can be both "Piano" and "Sad music".
        """
        per_window, frames, elapsed = [], 0, 0.0
        for window in windows_48k:
            audio = librosa.resample(window, orig_sr=SAMPLE_RATE, target_sr=YAMNET_SR)
            scores = []
            for start in range(0, max(len(audio) - FRAME, 0) + 1, HOP):
                frame = audio[start : start + FRAME]
                frame = np.pad(frame, (0, FRAME - len(frame))).astype(np.float32)
                begin = time.perf_counter()
                self.interpreter.set_tensor(self._input, frame)
                self.interpreter.invoke()
                scores.append(self.interpreter.get_tensor(self._output)[0].copy())
                elapsed += time.perf_counter() - begin
            per_window.append(np.stack(scores))
            frames += len(scores)
        return per_window, elapsed * 1000 / frames

    def window_scores(self, windows_48k: list[np.ndarray]) -> tuple[np.ndarray, float]:
        """Mean class scores per window, shape (n_windows, 521), + ms per frame."""
        per_window, ms = self.frame_scores(windows_48k)
        return np.stack([f.mean(axis=0) for f in per_window]), ms

    def scores(self, windows_48k: list[np.ndarray]) -> tuple[np.ndarray, float]:
        """Mean class scores over the whole track (windows are equal length)."""
        per_window, ms = self.window_scores(windows_48k)
        return per_window.mean(axis=0), ms

    def mood_scores(self, scores: np.ndarray) -> dict[str, float]:
        """Scores for the 5 backend labels, read off YAMNet's mood classes."""
        return {label: float(scores[i]) for i, label in self.mood_index.items()}

    def top_tags(self, scores: np.ndarray, k: int = 5) -> list[str]:
        """Most confident specific classes, e.g. instruments and vocals.

        These are the "sound facts" narration currently has no source for.
        """
        ranked = np.argsort(scores)[::-1]
        names = (self.class_names[i] for i in ranked)
        return [n for n in names if n not in GENERIC_CLASSES][:k]
