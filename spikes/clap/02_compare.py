"""Step 2: compare the backend's rule-based mood vs CLAP vs YAMNet.

For every track in data/tracks.csv this runs:

  1. baseline  - the real backend classifier (librosa features -> valence/
                 energy -> 5 labels), imported straight from moodtune-backend.
  2. CLAP      - zero-shot: embed the audio, embed text prompts for each
                 label, and pick the label whose prompts are most similar.

  3. YAMNet    - a 4 MB AudioSet classifier whose 521 classes include
                 "Happy music", "Sad music", etc. (see yamnet.py).

and grades each method against the Jamendo-tag bucket.

    .venv/bin/python 02_compare.py                 # everything
    .venv/bin/python 02_compare.py --models general yamnet
"""

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import librosa
import numpy as np
import torch
from transformers import ClapModel, ClapProcessor

from audio import load_windows
from yamnet import YamNet

from common import (
    BACKEND_DIR,
    BACKEND_TO_BUCKET,
    BUCKETS,
    DATA_DIR,
    LABEL_WORDS,
    LOGIT_SCALE_OVERRIDE,
    MODELS,
    PROMPT_TEMPLATES,
    RESULTS_DIR,
    SAMPLE_RATE,
    SINGLE_PROMPT,
    TRACKS_CSV,
)

LABELS = list(LABEL_WORDS)


# --------------------------------------------------------------------------- #
#  Baseline: the backend's rule-based classifier                               #
# --------------------------------------------------------------------------- #


def run_baseline(tracks: list[dict]) -> dict[str, str]:
    """Runs AudioAnalysisService exactly as /audio-upload/analyze does.

    Cached in results/baseline.json (~7 s/track); delete it to re-run.
    """
    cache = RESULTS_DIR / "baseline.json"
    labels = json.loads(cache.read_text()) if cache.exists() else {}
    if all(t["id"] in labels for t in tracks):
        return labels

    sys.path.insert(0, str(BACKEND_DIR))
    from app.services.audio_analysis_service import AudioAnalysisService

    service = AudioAnalysisService()
    for track in tracks:
        path = DATA_DIR / track["path"]
        features = service.analyze_uploaded_audio(path.read_bytes(), path.name)
        labels[track["id"]] = service.determine_upload_mood(features)["primary_mood"]
    cache.write_text(json.dumps(labels))
    return labels


# --------------------------------------------------------------------------- #
#  CLAP                                                                        #
# --------------------------------------------------------------------------- #


@torch.inference_mode()
def text_embeddings(
    model: ClapModel, processor: ClapProcessor, ensemble: bool
) -> torch.Tensor:
    """One unit-length embedding per label: shape (len(LABELS), 512).

    With ensembling, each label's prompts are embedded, averaged, and
    re-normalised. These vectors never change, so on a device you would
    compute them once (here) and ship them as a small JSON file instead of
    the ~127 MB text encoder.
    """
    rows = []
    for label in LABELS:
        if ensemble:
            prompts = [t.format(w) for w in LABEL_WORDS[label] for t in PROMPT_TEMPLATES]
        else:
            prompts = [SINGLE_PROMPT.format(label)]
        tokens = processor.tokenizer(prompts, padding=True, return_tensors="pt")
        embeds = model.get_text_features(**tokens)
        rows.append(torch.nn.functional.normalize(embeds.mean(0), dim=-1))
    return torch.stack(rows)


@torch.inference_mode()
def audio_embedding(
    model: ClapModel, processor: ClapProcessor, windows: list[np.ndarray]
) -> tuple[torch.Tensor, float]:
    """Mean of the per-window embeddings, plus ms per window.

    The feature extractor turns each window into a (1001 x 64) log-mel
    spectrogram. On a phone you'd reimplement this exactly (STFT 1024,
    hop 480, Slaney mel 50-14000 Hz, dB) - it is the riskiest part to port.
    """
    inputs = processor.feature_extractor(
        windows, sampling_rate=SAMPLE_RATE, return_tensors="pt"
    )
    start = time.perf_counter()
    embeds = model.get_audio_features(**inputs)
    elapsed_ms = (time.perf_counter() - start) * 1000 / len(windows)
    return torch.nn.functional.normalize(embeds.mean(0), dim=-1), elapsed_ms


def classify(audio: torch.Tensor, text: torch.Tensor, scale: float) -> dict[str, float]:
    """Cosine similarity x temperature -> softmax over labels.

    The temperature only sharpens or flattens the probabilities; it never
    changes which label wins.
    """
    logits = scale * (text @ audio)
    probs = logits.softmax(dim=-1)
    return {label: float(p) for label, p in zip(LABELS, probs)}


def to_bucket(probs: dict[str, float]) -> str:
    """Bucket of the single most likely label, as the app maps backend moods.

    (Summing probabilities per bucket looks tempting but hands "upbeat" a
    head start: it's the only bucket made of two labels.)
    """
    return BACKEND_TO_BUCKET[max(probs, key=probs.get)]


def run_clap(name: str, tracks: list[dict], windows: dict[str, list]) -> dict:
    repo = MODELS[name]
    print(f"\n[{name}] loading {repo} ...")
    model = ClapModel.from_pretrained(repo).eval()
    processor = ClapProcessor.from_pretrained(repo)
    audio_params = sum(p.numel() for p in model.audio_model.parameters())
    audio_params += sum(p.numel() for p in model.audio_projection.parameters())

    scale = LOGIT_SCALE_OVERRIDE.get(name, model.logit_scale_a.exp().item())
    text_ensemble = text_embeddings(model, processor, ensemble=True)
    text_single = text_embeddings(model, processor, ensemble=False)
    # This is the file you'd ship to the device alongside the audio encoder.
    (RESULTS_DIR / f"text_embeddings_{name}.json").write_text(json.dumps({
        "model": repo,
        "logit_scale": scale,
        "labels": LABELS,
        "embeddings": text_ensemble.tolist(),
    }))

    per_track, latencies, audio_embeds = {}, [], {}
    for i, track in enumerate(tracks, 1):
        audio, ms = audio_embedding(model, processor, windows[track["id"]])
        audio_embeds[track["id"]] = audio
        latencies.append(ms)
        ensemble = classify(audio, text_ensemble, scale)
        single = classify(audio, text_single, scale)
        per_track[track["id"]] = {
            "label": max(ensemble, key=ensemble.get),
            "bucket": to_bucket(ensemble),
            "single_bucket": to_bucket(single),
            "probs": ensemble,
        }
        print(f"  {i:>2}/{len(tracks)} {track['name'][:30]:<30} -> {per_track[track['id']]['bucket']}")

    # Calibration: some prompts sit closer to *all* music than others, so one
    # or two labels win almost everything. Subtracting each label's mean
    # similarity across the tracks removes that bias. It uses no ground
    # truth, only the unlabeled audio; on a device you'd compute the means
    # once from a reference set and ship them with the text embeddings.
    sims = torch.stack([text_ensemble @ a for a in audio_embeds.values()])
    label_bias, label_std = sims.mean(0), sims.std(0)
    for track_id, a in audio_embeds.items():
        per_track[track_id]["z"] = dict(zip(LABELS, ((text_ensemble @ a - label_bias) / label_std).tolist()))
        calibrated = (text_ensemble @ a - label_bias) * scale
        probs = dict(zip(LABELS, calibrated.softmax(-1).tolist()))
        per_track[track_id]["calibrated_bucket"] = to_bucket(probs)
        per_track[track_id]["calibrated_label"] = max(probs, key=probs.get)

    return {
        "tracks": per_track,
        "audio_params_m": audio_params / 1e6,
        "ms_per_window": float(np.median(latencies)),
    }


def run_yamnet(tracks: list[dict], windows: dict[str, list]) -> dict:
    print("\n[yamnet] loading models/yamnet.tflite ...")
    yamnet = YamNet()
    per_track, latencies, log_moods = {}, [], {}
    for i, track in enumerate(tracks, 1):
        scores, ms = yamnet.scores(windows[track["id"]])
        latencies.append(ms)
        moods = yamnet.mood_scores(scores)
        log_moods[track["id"]] = {k: np.log(v + 1e-9) for k, v in moods.items()}
        per_track[track["id"]] = {
            "label": max(moods, key=moods.get),
            "bucket": to_bucket(moods),
            "scores": moods,
            "tags": yamnet.top_tags(scores),
        }
        print(f"  {i:>2}/{len(tracks)} {track['name'][:30]:<30} -> {per_track[track['id']]['bucket']}")

    # Same calibration idea as CLAP: AudioSet has far more "Happy music"
    # than "Angry music", so raw scores lean on the common classes.
    # Centre each class's log-score on its mean across tracks.
    bias = {label: np.mean([m[label] for m in log_moods.values()]) for label in LABELS}
    std = {label: np.std([m[label] for m in log_moods.values()]) for label in LABELS}
    for track_id, moods in log_moods.items():
        centred = {label: moods[label] - bias[label] for label in LABELS}
        per_track[track_id]["z"] = {label: centred[label] / std[label] for label in LABELS}
        per_track[track_id]["calibrated_label"] = max(centred, key=centred.get)
        per_track[track_id]["calibrated_bucket"] = to_bucket(centred)

    return {"tracks": per_track, "ms_per_frame": float(np.median(latencies))}


def blend(*per_track_z: dict[str, float]) -> str:
    """Equal-weight sum of per-label z-scores from several models.

    Each model's scores were standardised per label across the tracks (no
    ground truth used), so they're on a common scale and nothing is tuned:
    there are no weights to overfit to this test set.
    """
    totals = {label: sum(z[label] for z in per_track_z) for label in LABELS}
    return to_bucket(totals)


# --------------------------------------------------------------------------- #
#  Reporting                                                                   #
# --------------------------------------------------------------------------- #


def accuracy(truth: list[str], predicted: list[str]) -> float:
    return sum(t == p for t, p in zip(truth, predicted)) / len(truth)


def balanced_accuracy(truth: list[str], predicted: list[str]) -> float:
    """Mean per-bucket recall, so a big bucket can't dominate."""
    recalls = []
    for b in BUCKETS:
        pairs = [(t, p) for t, p in zip(truth, predicted) if t == b]
        if pairs:
            recalls.append(sum(t == p for t, p in pairs) / len(pairs))
    return sum(recalls) / len(recalls)


def wilson(truth: list[str], predicted: list[str]) -> str:
    """Accuracy with a 95% Wilson interval, e.g. '50% (40-60)'."""
    n = len(truth)
    p = accuracy(truth, predicted)
    z = 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return f"{p:.0%} ({max(centre - half, 0):.0%}-{min(centre + half, 1):.0%})"


def confusion(truth: list[str], predicted: list[str]) -> str:
    """Rows = Jamendo tag bucket (truth), columns = prediction."""
    lines = ["| truth \\ predicted | " + " | ".join(BUCKETS) + " |",
             "|---" * (len(BUCKETS) + 1) + "|"]
    for t in BUCKETS:
        counts = [sum(1 for a, b in zip(truth, predicted) if a == t and b == p) for p in BUCKETS]
        lines.append(f"| **{t}** | " + " | ".join(str(c) for c in counts) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    methods = [*MODELS, "yamnet"]
    parser.add_argument("--models", nargs="+", default=methods, choices=methods)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    with TRACKS_CSV.open() as f:
        tracks = list(csv.DictReader(f))
    truth = [t["bucket"] for t in tracks]

    print(f"Baseline: backend rule-based classifier on {len(tracks)} tracks ...")
    start = time.perf_counter()
    baseline = run_baseline(tracks)
    baseline_s = (time.perf_counter() - start) / len(tracks)

    print("Decoding audio to 48 kHz windows ...")
    windows = {t["id"]: load_windows(DATA_DIR / t["path"]) for t in tracks}

    clap = {name: run_clap(name, tracks, windows) for name in args.models if name in MODELS}
    yamnet = run_yamnet(tracks, windows) if "yamnet" in args.models else None

    # Per-track CSV
    rows = []
    for track in tracks:
        row = {
            "id": track["id"], "name": track["name"], "artist": track["artist"],
            "truth": track["bucket"], "vartags": track["vartags"], "genres": track["genres"],
            "baseline_label": baseline[track["id"]],
            "baseline_bucket": BACKEND_TO_BUCKET[baseline[track["id"]]],
        }
        for name, result in clap.items():
            r = result["tracks"][track["id"]]
            row[f"{name}_label"] = r["label"]
            row[f"{name}_bucket"] = r["bucket"]
            row[f"{name}_single_prompt_bucket"] = r["single_bucket"]
            row[f"{name}_calibrated_bucket"] = r["calibrated_bucket"]
            row[f"{name}_probs"] = json.dumps({k: round(v, 3) for k, v in r["probs"].items()})
        if yamnet:
            r = yamnet["tracks"][track["id"]]
            row["yamnet_label"] = r["label"]
            row["yamnet_bucket"] = r["bucket"]
            row["yamnet_calibrated_bucket"] = r["calibrated_bucket"]
            row["yamnet_scores"] = json.dumps({k: round(v, 4) for k, v in r["scores"].items()})
            row["yamnet_tags"] = "|".join(r["tags"])
        if yamnet and "general" in clap:
            row["blend_bucket"] = blend(
                clap["general"]["tracks"][track["id"]]["z"], yamnet["tracks"][track["id"]]["z"]
            )
        rows.append(row)
    with (RESULTS_DIR / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    baseline_pred = [r["baseline_bucket"] for r in rows]
    lines = [
        "# Mood engines compared: rule-based vs CLAP vs YAMNet",
        "",
        f"{len(tracks)} Jamendo tracks: "
        + ", ".join(f"{b} {n}" for b, n in Counter(truth).items()) + ". "
        "Truth = the bucket implied by the track's Jamendo mood tags (noisy). "
        f"Chance = {1 / len(BUCKETS):.0%}.",
        "",
        "Accuracy shows a 95% confidence interval; balanced = mean per-bucket recall.",
        "",
        "| Method | Accuracy (95% CI) | Balanced | Model | CPU time |",
        "|---|---|---|---|---|",
        f"| Rule-based (backend) | {wilson(truth, baseline_pred)} | "
        f"{balanced_accuracy(truth, baseline_pred):.0%} | - | "
        + (f"{baseline_s * 1000:.0f} ms / whole track |" if baseline_s > 0.01 else "~7.5 s / whole track (cached) |"),
    ]
    for name, result in clap.items():
        ens = [r[f"{name}_bucket"] for r in rows]
        single = [r[f"{name}_single_prompt_bucket"] for r in rows]
        lines.append(
            f"| CLAP {name} (prompt ensemble) | {wilson(truth, ens)} | {balanced_accuracy(truth, ens):.0%} | "
            f"{result['audio_params_m']:.0f}M params | {result['ms_per_window']:.0f} ms / 10 s window |"
        )
        calibrated = [r[f"{name}_calibrated_bucket"] for r in rows]
        lines.append(f"| CLAP {name} (single prompt) | {wilson(truth, single)} | "
                     f"{balanced_accuracy(truth, single):.0%} | | |")
        lines.append(f"| CLAP {name} (ensemble + calibrated) | {wilson(truth, calibrated)} | "
                     f"{balanced_accuracy(truth, calibrated):.0%} | | |")

    if yamnet:
        raw = [r["yamnet_bucket"] for r in rows]
        calibrated = [r["yamnet_calibrated_bucket"] for r in rows]
        lines.append(
            f"| YAMNet (raw) | {wilson(truth, raw)} | {balanced_accuracy(truth, raw):.0%} | "
            "4 MB tflite (3.7M params) | "
            f"{yamnet['ms_per_frame']:.1f} ms / 0.975 s frame |"
        )
        lines.append(f"| YAMNet (calibrated) | {wilson(truth, calibrated)} | "
                     f"{balanced_accuracy(truth, calibrated):.0%} | | |")
    if rows and "blend_bucket" in rows[0]:
        blended = [r["blend_bucket"] for r in rows]
        lines.append(f"| **CLAP general + YAMNet blend** | {wilson(truth, blended)} | "
                     f"{balanced_accuracy(truth, blended):.0%} | 34 + 4 MB | |")

    lines += ["", "## Confusion matrices", "", "### Rule-based (backend)", "",
              confusion(truth, baseline_pred), "",
              f"Backend label distribution: {dict(Counter(baseline.values()))}"]
    for name in clap:
        lines += ["", f"### CLAP {name}", "", confusion(truth, [r[f'{name}_bucket'] for r in rows]), "",
                  f"CLAP {name} label distribution: {dict(Counter(r[f'{name}_label'] for r in rows))}",
                  "", f"### CLAP {name}, calibrated", "",
                  confusion(truth, [r[f'{name}_calibrated_bucket'] for r in rows])]

    if yamnet:
        lines += ["", "### YAMNet (raw)", "", confusion(truth, [r["yamnet_bucket"] for r in rows]), "",
                  f"YAMNet label distribution: {dict(Counter(r['yamnet_label'] for r in rows))}",
                  "", "### YAMNet (calibrated)", "",
                  confusion(truth, [r["yamnet_calibrated_bucket"] for r in rows]),
                  "", "## YAMNet sound tags (sample)", "",
                  "| Track | Truth | Top tags |", "|---|---|---|"]
        lines += [f"| {r['name'][:30]} | {r['truth']} | {r['yamnet_tags'].replace('|', ', ')} |"
                  for r in rows[::5]]

    if rows and "blend_bucket" in rows[0]:
        lines += ["", "### CLAP general + YAMNet blend", "",
                  confusion(truth, [r["blend_bucket"] for r in rows])]

    summary = "\n".join(lines) + "\n"
    (RESULTS_DIR / "summary.md").write_text(summary)
    print("\n" + summary)


if __name__ == "__main__":
    main()
