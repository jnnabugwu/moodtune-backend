# CLAP mood spike

Question: is CLAP (Contrastive Language-Audio Pretraining) better at mood than
the backend's rule-based classifier, and is the music checkpoint worth ~2.3x
the size of the general one? Answer that before building anything on-device.

## How CLAP classifies without being trained on your labels

CLAP is two encoders trained so matching audio and captions land close
together in the same 512-d space:

```
audio  -> 48 kHz mono -> 10 s window -> log-mel (1001 x 64) -> HTSAT audio encoder -> 512-d vector
text   -> "This audio is a sad song." -> RoBERTa text encoder ---------------------> 512-d vector
```

Zero-shot classification = embed the audio once, embed one prompt per label,
take cosine similarity, scale by the model's learned temperature, softmax.
Whichever label's prompt is closest wins. Nothing is trained here.

Two details that matter for shipping it:

- **Text embeddings are constant.** For a fixed label set you compute them
  once (`results/text_embeddings_*.json`) and ship ~10 KB of numbers instead
  of the ~127 MB text encoder. Only the audio encoder runs on the phone.
- **The log-mel front-end must match training exactly.** If an on-device
  reimplementation gets the STFT, mel filters or dB scaling slightly wrong,
  the model still returns confident-looking garbage. No error is raised.

## Files

| File | What it does |
|---|---|
| `common.py` | Labels, prompts, model ids, paths. Edit prompts here. |
| `01_fetch_tracks.py` | Downloads 10 CC tracks per mood bucket from Jamendo and labels them from their mood tags. |
| `yamnet.py` | Runs YAMNet from its 4 MB `.tflite` with LiteRT, the same file and runtime a phone would use. |
| `02_compare.py` | Runs the backend classifier, both CLAP models, and YAMNet on every track, then writes `results/`. |
| `audio.py` | Decodes a track to mono 48 kHz and cuts the three 10 s windows. |
| `03_tag_sheet.py` | Builds `results/tag_sheet.html`: a listening page for choosing sound-tag wording. |
| `swift_parity/` | Builds the app's `AudioWindowDecoder.swift` as a macOS CLI and checks it against librosa: 20/20 mood labels match, worst YAMNet score diff 0.005, all 5 upload formats decode. |
| `results/summary.md` | Accuracy, latency, and confusion matrices. |
| `results/results.csv` | Per-track predictions and CLAP label probabilities. |

## Run

This spike is committed at `spikes/clap/` in both `moodtune_app` and
`moodtune-backend`. Scripts find the other repo as a sibling folder (set
`MOODTUNE_APP` / `MOODTUNE_BACKEND` otherwise). `02_compare.py` imports the
backend's classifier; `01_fetch_tracks.py` reads `JAMENDO_CLIENT_ID` from the
app's `dev.env`; `04_export_app_assets.py` writes the app's YAMNet assets.

Audio (`data/tracks/`), models, the venv and `results/yamnet_frame_scores.npz`
aren't committed; the commands below recreate them (`03_tag_sheet.py`
rewrites the `.npz`).

```sh
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python 01_fetch_tracks.py --per-bucket 10
curl -sLo models/yamnet.tflite https://storage.googleapis.com/mediapipe-models/audio_classifier/yamnet/float32/1/yamnet.tflite
curl -sLo models/yamnet_class_map.csv https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv
.venv/bin/python 02_compare.py            # or: --models general yamnet
```

## Things to try

- **Prompts.** Change `LABEL_WORDS` / `PROMPT_TEMPLATES` in `common.py`
  and re-run. Compare the "single prompt" rows with the "prompt ensemble" rows
  to see how much wording alone moves accuracy.
- **Windows.** Set `WINDOW_POSITIONS = [0.5]` to see how much averaging
  three 10 s windows helps versus one.
- **Read the misses.** Sort `results.csv` by `truth`. Many "misses" are tag
  noise: listen to a few on Jamendo before trusting the numbers.

## Findings (200 tracks, 2026-10-13)

50 tracks per bucket. Chance is 25%. Brackets are 95% confidence intervals.

| Method | Accuracy | Size | Time per track (M4 Pro CPU) |
|---|---|---|---|
| Rule-based backend | 32% (26-39) | - | ~7.4 s |
| **CLAP general, calibrated** | **50% (44-57)** | 34 MB int8 | ~60 ms |
| CLAP general + YAMNet blend | 48% (41-55) | 38 MB | ~90 ms |
| YAMNet, raw or calibrated | 44% (37-51) | **4 MB** | ~30 ms |
| CLAP music, best variant | 28% (23-35) | ~78 MB int8 | ~100 ms |

1. **CLAP general clearly beats the rule-based engine.** Their intervals don't
   overlap. The backend almost never predicts charged (3/50) and calls 34/50
   serene tracks reflective.
2. **YAMNet is the size/accuracy bargain.** It's 6 points behind CLAP (within
   the noise) at a tenth of the size, with no spectrogram code to port.
3. **The blend didn't help.** On 40 tracks the two models looked complementary.
   At 200 that was mostly noise. Good reminder of why the bigger set mattered.
4. **CLAP music is at chance.** With calibration it still can't separate
   anything. Together with its broken temperature (below), that points to a
   bad Hugging Face conversion, not a bad model. Test LAION's original
   `music_audioset_epoch_15_esc_90.14.pt` via `laion_clap` before writing it off.
5. **Serene vs reflective is the hard pair for every model.** Calibrated CLAP
   sends 20/50 reflective tracks to serene. Both are slow and soft; they differ
   in *valence*, and music-emotion research consistently finds audio predicts
   energy (arousal) much better than valence. Some of it is also tag noise.

### About YAMNet

Google's AudioSet classifier: 4 MB, 3.7M params, raw 16 kHz audio in, 521
class scores out. Five classes are moods (`Happy`, `Exciting`, `Tender`,
`Angry`, `Sad music`), mapped onto the backend's labels in `common.py`.

- **No front-end to port.** The spectrogram lives inside the `.tflite`.
- **Sound tags are half useful.** Instruments and vocal types (`Acoustic
  guitar`, `Singing`, `Rapping`) look right and are exactly the facts narration
  lacks. Genre-ish classes are noisy (`Christian music`, `Christmas music`,
  `Lullaby` on pop tracks), so narration would need an allowlist plus a
  score threshold.

### Lessons from building the spike

1. **Label bias dominates raw zero-shot.** Without calibration, CLAP general
   rarely picks serene because "energetic"/"angry" prompts sit closer to all
   music. Centring each label's similarity on its mean across tracks fixed it
   (37% -> 50%). It uses no ground truth; on a device you'd ship the means.
2. **`laion/larger_clap_music` ships a broken temperature** (`logit_scale_a`
   = 0.027 in the weights, so softmax ~ 0.2 for every label). Ranking still
   works, but probabilities are meaningless unless overridden.
3. **Summing label probabilities per bucket is biased** toward buckets made of
   more labels (upbeat = happy + energetic). Use the top label's bucket.
4. **Small test sets lie.** At 40 tracks the CIs spanned ~30 points and
   suggested a blend would help. At 200 it didn't.

### Sound tags: pool by peak, not by average

YAMNet's instrument and vocal scores on full mixes are tiny when averaged over
a track (median "Singing" score 0.009). At a 0.1 cutoff:

| Pooling | Tracks with 2-3 tags | Tracks with none |
|---|---|---|
| Mean over frames | 3% | 87% |
| 90th percentile | 16% | 75% |
| **Peak frame** | **52%** | 32% |

Tags therefore use each class's peak frame score (`03_tag_sheet.py`). Peak
pooling is more prone to one-frame false positives; the listening sheet is how
we check. Mood stays on mean pooling, which is what was evaluated.

## Caveats

- 200 tracks still gives +/-7 point intervals. Differences under ~10 points
  between methods aren't settled.
- Jamendo tags are written by artists, so "truth" is noisy. Upbeat vs
  charged and serene vs reflective are genuinely blurry.
- Latency is PyTorch on an M4 Pro CPU, not a phone, and not quantized.

## Next steps

1. **ONNX export + int8 quantization** of the winning audio encoder. Check
   that the quantized model gives the same answers as PyTorch (cosine > 0.99
   on these tracks).
2. **Re-implement the log-mel front-end in plain numpy** and diff it against
   `ClapFeatureExtractor`. This is the piece you'd port to Swift/Kotlin/Dart,
   so it's the best place to learn where the parity traps are.
