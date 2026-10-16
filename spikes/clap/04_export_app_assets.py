"""Step 4: export what the app needs to run YAMNet mood + tags on device.

Writes into moodtune_app/:
  assets/models/yamnet.tflite        the model the spike evaluated (copy)
  assets/models/yamnet_mood.json     mood classes, calibration, tag allowlist
  test/features/on_device_mood/fixtures/yamnet_golden.json
                                     5 tracks' YAMNet scores + the label, probs
                                     and tags Python derives from them, so a
                                     Dart unit test can prove the app's logic
                                     matches this pipeline exactly
  integration_test/yamnet_signal_expected.dart
                                     expected scores for a synthetic test
                                     signal the app regenerates on a device
                                     (Dart, because a device can't read
                                     files from this Mac)

    .venv/bin/python 04_export_app_assets.py

Set MOODTUNE_APP to write into another checkout (e.g. a git worktree).
"""

import csv
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from audio import load_windows
from common import APP_DIR, BACKEND_TO_BUCKET, DATA_DIR, ROOT, TRACKS_CSV, YAMNET_MOOD_CLASSES
from yamnet import FRAME, HOP, MODEL_PATH, YAMNET_SR, YamNet

APP = APP_DIR
SOURCE = "spikes/clap/04_export_app_assets.py"  # in moodtune_app and moodtune-backend
CONFIG_VERSION = 1
EPSILON = 1e-9
# Below this, no mood class registered on enough frames to mean anything (one
# frame at YAMNet's lowest output step is 1/256/57 = 6.9e-5). Softmax over
# epsilon-floored scores would otherwise call silence or a test tone "angry",
# the label with the lowest reference mean. 1 of the 200 Jamendo tracks falls
# below it.
MIN_MOOD_SCORE = 5e-4
# Extra expectation for the tag cutoff path: 15/256, a quantised YAMNet score,
# as the float32 a stored peak of 0.0585938 becomes in Dart. Some golden tags
# sit exactly on it and others miss it, so the fixture checks `>=` and that
# tags are both kept and dropped.
GOLDEN_THRESHOLD = float(np.float32(round(15 / 256, 7)))

# Synthetic device-test signal. The Dart integration test generates the same
# samples with the same formula, so no audio file has to be bundled.
SIGNAL_SR = 44_100
SIGNAL_SECONDS = 30
SIGNAL_TONES = [(220.0, 0.30), (277.18, 0.20), (329.63, 0.20)]  # A minor-ish chord
SIGNAL_PULSE_HZ = 2.0
SIGNAL_SCALE = 20_000


def synthetic_signal() -> np.ndarray:
    """int16 samples: a chord with a 2 Hz pulse. Mirrored in Dart."""
    t = np.arange(SIGNAL_SR * SIGNAL_SECONDS) / SIGNAL_SR
    chord = sum(a * np.sin(2 * np.pi * f * t) for f, a in SIGNAL_TONES)
    envelope = 0.6 + 0.4 * np.sin(2 * np.pi * SIGNAL_PULSE_HZ * t)
    return np.round(chord * envelope * SIGNAL_SCALE).astype(np.int16)


def track_scores(yamnet: YamNet, path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(mean, peak) class scores in float32, exactly as the spike pools them."""
    frames, _ = yamnet.frame_scores(load_windows(path))
    mean = np.mean([f.mean(axis=0) for f in frames], axis=0)  # mean of window means
    peak = np.max(np.concatenate(frames), axis=0)
    return mean.astype(np.float32), peak.astype(np.float32)


def interpret(mean: np.ndarray, peak: np.ndarray, config: dict, threshold: float | None) -> dict:
    """Reference implementation of what the Dart OnDeviceMoodClassifier does.

    primaryMood and probabilities are None when no mood class reaches
    minScore; tags are computed either way.
    """
    mood = config["mood"]
    tags = top_tags(peak, config, threshold)
    if max(float(mean[c["index"]]) for c in mood["classes"]) < mood["minScore"]:
        return {"primaryMood": None, "probabilities": None, "tags": tags}
    centred = {
        c["label"]: float(np.log(float(mean[c["index"]]) + EPSILON)) - mood["logScoreMeans"][c["label"]]
        for c in mood["classes"]
    }
    values = np.array(list(centred.values()))
    probs = np.exp(values - values.max())
    probs /= probs.sum()
    probs = dict(zip(centred, probs.tolist()))
    return {"primaryMood": max(probs, key=probs.get), "probabilities": probs, "tags": tags}


def top_tags(peak: np.ndarray, config: dict, threshold: float | None) -> list[str]:
    best: dict[str, float] = {}
    for c in config["tags"]["classes"]:
        score = float(peak[c["index"]])
        if score > best.get(c["tag"], -1):
            best[c["tag"]] = score
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    if threshold is not None:
        ranked = [kv for kv in ranked if kv[1] >= threshold]
    return [tag for tag, _ in ranked[: config["tags"]["max"]]]


def main() -> None:
    yamnet = YamNet()
    with TRACKS_CSV.open() as f:
        tracks = list(csv.DictReader(f))

    print(f"Scoring {len(tracks)} tracks for calibration ...")
    scores = [track_scores(yamnet, DATA_DIR / t["path"]) for t in tracks]
    mood_index = {label: yamnet.class_names.index(name) for name, label in YAMNET_MOOD_CLASSES.items()}
    log_means = {
        label: float(np.mean([np.log(mean[i] + EPSILON) for mean, _ in scores]))
        for label, i in mood_index.items()
    }

    decisions = json.loads((ROOT / "tag_decisions.json").read_text())
    config = {
        "version": CONFIG_VERSION,
        "source": SOURCE,
        "input": {"sampleRate": YAMNET_SR, "frameSamples": FRAME, "hopSamples": HOP},
        "mood": {
            "pooling": "mean",
            "epsilon": EPSILON,
            "minScore": MIN_MOOD_SCORE,
            # Per-label mean log-score over the 200 Jamendo tracks. Subtracting
            # it removes AudioSet's bias toward common classes ("Happy music").
            "logScoreMeans": log_means,
            "classes": [
                {"index": yamnet.class_names.index(name), "class": name, "label": label}
                for name, label in YAMNET_MOOD_CLASSES.items()
            ],
        },
        "tags": {
            "pooling": "peak",
            "threshold": None,  # strictness not decided yet: always top `max`
            "max": 3,
            "classes": [
                {"index": yamnet.class_names.index(name), "class": name, "tag": d["name"]}
                for name, d in decisions.items() if d["keep"]
            ],
        },
    }

    models = APP / "assets" / "models"
    models.mkdir(parents=True, exist_ok=True)
    shutil.copy(MODEL_PATH, models / "yamnet.tflite")
    (models / "yamnet_mood.json").write_text(json.dumps(config, indent=2) + "\n")

    # Golden fixtures: one track per predicted label, plus one with no mood
    # (primaryMood None) to check the minScore guard.
    golden, seen = [], set()
    for track, (mean, peak) in zip(tracks, scores):
        # Expectations come from the rounded vectors the fixture stores, read
        # into float32 as Dart's Float32Lists do, so rounding can't make Python
        # and Dart disagree (e.g. on a tag exactly at the cutoff).
        mean = np.round(mean.astype(np.float64), 7)
        peak = np.round(peak.astype(np.float64), 7)
        mean32, peak32 = mean.astype(np.float32), peak.astype(np.float32)
        result = interpret(mean32, peak32, config, None)
        if result["primaryMood"] in seen:
            continue
        seen.add(result["primaryMood"])
        golden.append({
            "track": track["name"],
            "mean": [float(x) for x in mean],
            "peak": [float(x) for x in peak],
            "expected": result,
            "expectedTagsAtThreshold": interpret(mean32, peak32, config, GOLDEN_THRESHOLD)["tags"],
        })
        if len(seen) == len(YAMNET_MOOD_CLASSES) + 1:
            break
    cut = [(g["expected"]["tags"], g["expectedTagsAtThreshold"]) for g in golden]
    assert any(kept for _, kept in cut), "no tag reaches GOLDEN_THRESHOLD"
    assert any(kept != tags for tags, kept in cut), "GOLDEN_THRESHOLD drops no tag"
    fixtures = APP / "test" / "features" / "on_device_mood" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    # Pretty-printed, one value per line, so a regeneration's diff shows
    # exactly which scores or expectations moved.
    (fixtures / "yamnet_golden.json").write_text(json.dumps({
        "version": CONFIG_VERSION, "source": SOURCE,
        "threshold": GOLDEN_THRESHOLD, "tracks": golden,
    }, indent=2) + "\n")

    # Device test: expected scores for the synthetic signal.
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "signal.wav"
        sf.write(wav, synthetic_signal(), SIGNAL_SR, subtype="PCM_16")
        mean, peak = track_scores(yamnet, wav)
    top = np.argsort(mean)[::-1][:10]
    watched = sorted(set(top.tolist()) | set(mood_index.values()))
    signal = {
        "sampleRate": SIGNAL_SR, "seconds": SIGNAL_SECONDS,
        "tones": [{"hz": f, "amplitude": a} for f, a in SIGNAL_TONES],
        "pulseHz": SIGNAL_PULSE_HZ, "scale": SIGNAL_SCALE,
        "classes": [
            {"index": int(i), "class": yamnet.class_names[i],
             "mean": round(float(mean[i]), 6), "peak": round(float(peak[i]), 6)}
            for i in watched
        ],
        "expected": interpret(mean, peak, config, None),
    }
    out = APP / "integration_test" / "yamnet_signal_expected.dart"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        f"// Generated by {SOURCE}. Do not edit.\n"
        "// Expected YAMNet output for the synthetic signal in yamnet_device_test.dart.\n\n"
        f"const yamnetSignalExpectedJson = '''\n{json.dumps(signal, indent=2)}\n''';\n"
    )

    print("log-score means:", {k: round(v, 3) for k, v in log_means.items()})
    print("golden labels:", [g["expected"]["primaryMood"] for g in golden])
    print("golden tags at threshold:", [g["expectedTagsAtThreshold"] for g in golden])
    print("signal top classes:", [yamnet.class_names[i] for i in top[:5]], "→", signal["expected"])
    print("buckets covered:", sorted({
        BACKEND_TO_BUCKET[g["expected"]["primaryMood"]] for g in golden if g["expected"]["primaryMood"]
    }))


if __name__ == "__main__":
    main()
