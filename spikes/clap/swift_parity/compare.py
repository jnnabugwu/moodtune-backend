"""Parity check: the app's Swift AudioWindowDecoder vs the spike's librosa path.

For each track, decodes the three windows with both and compares:
  - window start times
  - the PCM itself (correlation after aligning, level ratio, lag)
  - what actually matters: YAMNet's class scores and mood label

Also converts a few tracks to every upload format (m4a, wav, flac, ogg) to
check each one decodes, or fails cleanly (ogg on Apple platforms).

    swiftc -O <moodtune_app>/ios/Runner/AudioWindowDecoder.swift main.swift -o decode
    ../.venv/bin/python compare.py
"""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from audio import load_windows_with_starts  # noqa: E402
from common import DATA_DIR, TRACKS_CSV  # noqa: E402
from yamnet import YAMNET_SR, YamNet  # noqa: E402

DECODE = HERE / "decode"
TRACKS_PER_BUCKET = 5
MAX_LAG = 2000  # samples at 16 kHz (125 ms): MP3 decoders differ on encoder delay


def swift_decode(path: Path, out: Path) -> dict:
    subprocess.run([DECODE, path, out], check=True)
    meta = json.loads((out / "meta.json").read_text())
    if "error" not in meta:
        meta["windows"] = [
            np.fromfile(out / f"window_{i}.f32", dtype="<f4") for i in range(len(meta["startSeconds"]))
        ]
    return meta


def librosa_decode(path: Path) -> tuple[list[np.ndarray], list[float]]:
    """Exactly what the spike fed YAMNet: 48 kHz windows, resampled to 16 kHz."""
    windows, starts = load_windows_with_starts(path)
    return [librosa.resample(w, orig_sr=48_000, target_sr=YAMNET_SR) for w in windows], starts


def align(a: np.ndarray, b: np.ndarray) -> tuple[int, float]:
    """Lag (samples) that best aligns b to a, and the correlation at that lag."""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    spectrum = np.fft.rfft(a, 2 * n) * np.conj(np.fft.rfft(b, 2 * n))
    xcorr = np.fft.irfft(spectrum)
    lags = np.r_[np.arange(0, MAX_LAG + 1), np.arange(-MAX_LAG, 0)]
    values = np.r_[xcorr[: MAX_LAG + 1], xcorr[-MAX_LAG:]]
    lag = int(lags[np.argmax(values)])
    if lag >= 0:
        x, y = a[lag:], b[: n - lag]
    else:
        x, y = a[: n + lag], b[-lag:]
    return lag, float(np.corrcoef(x, y)[0, 1])


def frame_mean(yamnet: YamNet, windows_16k: list[np.ndarray]) -> np.ndarray:
    """YAMNet mean scores from 16 kHz windows (yamnet.py takes 48 kHz input)."""
    up = [librosa.resample(w, orig_sr=YAMNET_SR, target_sr=48_000) for w in windows_16k]
    return yamnet.scores(up)[0]


def main() -> None:
    if not DECODE.exists():
        sys.exit("Build the harness first (see docstring).")
    with TRACKS_CSV.open() as f:
        tracks = list(csv.DictReader(f))
    by_bucket: dict[str, list[dict]] = {}
    for t in tracks:
        by_bucket.setdefault(t["bucket"], []).append(t)
    sample = [t for ts in by_bucket.values() for t in ts[:TRACKS_PER_BUCKET]]

    yamnet = YamNet()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for t in sample:
            path = DATA_DIR / t["path"]
            swift = swift_decode(path, tmp / t["id"])
            ref_windows, ref_starts = librosa_decode(path)

            lags, corrs, levels = [], [], []
            for s, r in zip(swift["windows"], ref_windows):
                lag, corr = align(r, s)
                lags.append(lag)
                corrs.append(corr)
                levels.append(float(np.sqrt(np.mean(s**2)) / np.sqrt(np.mean(r**2))))

            ref_scores = frame_mean(yamnet, ref_windows)
            swift_scores = frame_mean(yamnet, swift["windows"])
            ref_mood = yamnet.mood_scores(ref_scores)
            swift_mood = yamnet.mood_scores(swift_scores)
            rows.append({
                "track": t["name"][:28],
                "start_diff_ms": max(abs(a - b) for a, b in zip(swift["startSeconds"], ref_starts)) * 1000,
                "lag_ms": max(abs(x) for x in lags) / YAMNET_SR * 1000,
                "corr": min(corrs),
                "level": float(np.mean(levels)),
                "max_score_diff": float(np.abs(ref_scores - swift_scores).max()),
                "same_mood": max(ref_mood, key=ref_mood.get) == max(swift_mood, key=swift_mood.get),
                "ms": swift["elapsedMs"],
            })

        print(f"{'track':<30}{'start Δms':>10}{'lag ms':>8}{'corr':>7}{'level':>7}{'max Δscore':>11}{'mood':>6}{'ms':>6}")
        for r in rows:
            print(f"{r['track']:<30}{r['start_diff_ms']:>10.1f}{r['lag_ms']:>8.1f}{r['corr']:>7.3f}"
                  f"{r['level']:>7.3f}{r['max_score_diff']:>11.4f}{'✓' if r['same_mood'] else '✗':>6}{r['ms']:>6.0f}")
        agree = sum(r["same_mood"] for r in rows)
        print(f"\nMood label agrees on {agree}/{len(rows)} tracks; "
              f"worst YAMNet score diff {max(r['max_score_diff'] for r in rows):.4f}; "
              f"median decode {np.median([r['ms'] for r in rows]):.0f} ms")

        check_formats(DATA_DIR / sample[0]["path"], tmp)


def check_formats(source: Path, tmp: Path) -> None:
    """Decodes the same 60 s clip saved in every upload format the app accepts."""
    print("\nFormats (same 60 s clip in each format, compared with the wav):")
    audio, sr = librosa.load(source, sr=None, mono=False, duration=60)
    frames = np.ascontiguousarray(audio.T)
    wav = tmp / "fmt.wav"
    sf.write(wav, frames, sr)
    # libsndfile's Vorbis encoder overflows the thread stack on one huge
    # write, so write the ogg in small chunks.
    with sf.SoundFile(tmp / "fmt.ogg", "w", sr, frames.shape[1], format="OGG", subtype="VORBIS") as ogg:
        for i in range(0, len(frames), 4096):
            ogg.write(frames[i : i + 4096])
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", wav, tmp / "fmt.m4a"], check=True)
    subprocess.run(["afconvert", "-f", "flac", "-d", "flac", wav, tmp / "fmt.flac"], check=True)
    subprocess.run(["afconvert", "-f", "MPG3", "-d", ".mp3", wav, tmp / "fmt.mp3"],
                   check=False, capture_output=True)  # macOS may lack an MP3 encoder

    reference = swift_decode(wav, tmp / "ref_wav")
    for ext in ["mp3", "m4a", "wav", "flac", "ogg"]:
        path = tmp / f"fmt.{ext}"
        if not path.exists():
            print(f"  {ext:<5} → no encoder on this Mac; covered by the 20-track test above")
            continue
        result = swift_decode(path, tmp / f"out_{ext}")
        if "error" in result:
            print(f"  {ext:<5} → error '{result['error']}': {result['message'][:70]}")
            continue
        corr = min(align(r, s)[1] for r, s in zip(reference["windows"], result["windows"]))
        print(f"  {ext:<5} → {len(result['windows'])} windows, {result['sourceSampleRate']:.0f} Hz "
              f"{result['channelCount']} ch, corr vs wav {corr:.3f}, {result['elapsedMs']:.0f} ms")


if __name__ == "__main__":
    main()
