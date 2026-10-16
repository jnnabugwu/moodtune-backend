"""Shared constants for the CLAP spike: labels, prompts, paths, models."""

import os
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
TRACKS_DIR = DATA_DIR / "tracks"
TRACKS_CSV = DATA_DIR / "tracks.csv"
RESULTS_DIR = ROOT / "results"



def _repo(env: str, name: str, marker: str) -> Path:
    """The spike lives at spikes/clap in both moodtune_app and moodtune-backend.

    Finds `name` as this repo, a subfolder of it, or a sibling of it, by its
    `marker` file. Set `env` to point somewhere else.
    """
    if env in os.environ:
        return Path(os.environ[env])
    repo = ROOT.parents[1]
    for candidate in (repo, repo / name, repo.parent / name):
        if (candidate / marker).exists():
            return candidate
    raise SystemExit(f"Can't find {name}; set {env}")


APP_DIR = _repo("MOODTUNE_APP", "moodtune_app", "pubspec.yaml")
BACKEND_DIR = _repo("MOODTUNE_BACKEND", "moodtune-backend", "alembic.ini")
APP_ENV = APP_DIR / "dev.env"

# CLAP checkpoints to compare. Both use the same preprocessing (48 kHz,
# 10 s windows, 64 mel bins); they differ in audio encoder size + training data.
MODELS = {
    "general": "laion/clap-htsat-unfused",  # HTSAT-tiny, mostly sound events
    "music": "laion/larger_clap_music",  # HTSAT-base, + music collections
}

# Learned softmax temperature override. The published larger_clap_music
# weights store logit_scale_a = 0.027 (exp -> ~1.03, vs ~18.7 for the general
# model), which flattens every softmax to ~0.2 per label. Ranking is
# unaffected; only probabilities. We fall back to CLAP's init value, 1/0.07.
LOGIT_SCALE_OVERRIDE = {"music": 1 / 0.07}

# The backend's 5 labels (audio_analysis_service.py) collapse into the app's
# 4 display buckets (mood_theme.dart). We grade at the bucket level because
# that's what users see, and "happy" vs "energetic" is too blurry to grade.
BACKEND_TO_BUCKET = {
    "happy": "upbeat",
    "energetic": "upbeat",
    "calm": "serene",
    "angry": "charged",
    "sad": "reflective",
}
BUCKETS = ["upbeat", "serene", "charged", "reflective"]

# Jamendo "vartags" that count as evidence for each bucket. A track is only
# used if its tags point at exactly one bucket.
BUCKET_TAGS = {
    "upbeat": {"happy", "joyful", "cheerful", "upbeat", "fun", "positive", "euphoric"},
    "serene": {"relaxing", "calm", "peaceful", "chill", "meditation", "soothing", "relax"},
    "charged": {"angry", "aggressive", "furious", "rage"},
    "reflective": {"sad", "sadness", "melancholic", "melancholy", "sorrow", "nostalgic"},
}
# Searches used to find candidates for each bucket (Jamendo query params).
BUCKET_QUERIES = {
    "upbeat": [{"tags": "happy"}, {"fuzzytags": "happy"}],
    "serene": [{"fuzzytags": "relaxing"}, {"fuzzytags": "peaceful"}],
    "charged": [{"tags": "angry"}, {"fuzzytags": "aggressive"}],
    "reflective": [{"tags": "melancholic"}, {"fuzzytags": "sad"}, {"tags": "sadness"}],
}

# Zero-shot prompts. CLAP compares the audio embedding with a text embedding
# per prompt; we average several phrasings per label ("prompt ensembling")
# because a single wording is noisy.
LABEL_WORDS = {
    "happy": ["happy", "joyful", "cheerful"],
    "energetic": ["energetic", "high-energy", "upbeat and driving"],
    "calm": ["calm", "relaxing", "peaceful"],
    "angry": ["angry", "aggressive", "intense and heavy"],
    "sad": ["sad", "melancholic", "sorrowful"],
}
PROMPT_TEMPLATES = [
    "This audio is a {} song.",  # the template LAION used for GTZAN
    "{} music.",
    "A {} piece of music.",
]
# Baseline for comparison: one prompt per label, no ensembling.
SINGLE_PROMPT = "This audio is a {} song."

# YAMNet (AudioSet) mood classes mapped onto the backend's 5 labels. AudioSet
# also has "Scary music" and "Funny music"; they don't fit any label, so
# they're left out. "Tender" (soft, gentle) is the closest thing to calm.
YAMNET_MOOD_CLASSES = {
    "Happy music": "happy",
    "Exciting music": "energetic",
    "Tender music": "calm",
    "Angry music": "angry",
    "Sad music": "sad",
}

# Sound-tag candidates (decided 2026-10-16): instruments, vocals collapsed to
# one "vocals" tag, and three genres. Values are *suggested* display names;
# the final wording is chosen by ear on results/tag_sheet.html.
TAG_VOCAL_CLASSES = [
    "Singing", "Choir", "Child singing", "Synthetic singing", "Rapping",
    "Humming", "Vocal music", "A capella",
]
TAG_GENRE_CLASSES = {"Hip hop music": "hip hop", "Heavy metal": "metal", "Jazz": "jazz"}
# Instruments are one contiguous block of YAMNet's class map, minus classes
# that are techniques or non-musical sounds.
TAG_INSTRUMENT_BLOCK = ("Plucked string instrument", "Singing bowl")
TAG_INSTRUMENT_EXCLUDE = {
    "Tapping (guitar technique)", "Bicycle bell", "Tuning fork",
    "Change ringing (campanology)", "Church bell", "Jingle bell", "Shofar",
}
TAG_NAME_SUGGESTIONS = {
    "Plucked string instrument": "plucked strings",
    "Steel guitar, slide guitar": "slide guitar",
    "Keyboard (musical)": "keys",
    "Hammond organ": "organ",
    "Electronic organ": "organ",
    "Synthesizer": "synths",
    "Drum kit": "drums",
    "Drum": "drums",
    "Snare drum": "drums",
    "Bass drum": "drums",
    "Rattle (instrument)": "rattle",
    "Marimba, xylophone": "marimba",
    "Bowed string instrument": "strings",
    "String section": "strings",
    "Violin, fiddle": "violin",
    "Brass instrument": "brass",
    "Wind instrument, woodwind instrument": "woodwinds",
}

SAMPLE_RATE = 48_000
WINDOW_SECONDS = 10
# Where in the track to take 10 s windows (fractions of duration). The
# embeddings are averaged, so the verdict isn't based on just the intro.
WINDOW_POSITIONS = [0.25, 0.5, 0.75]
