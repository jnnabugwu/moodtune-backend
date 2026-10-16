"""Step 3: build a listening sheet for choosing sound-tag wording.

For every candidate class (instruments, vocals, hip hop / metal / jazz) that
would actually show up as one of a track's top 3 tags, the sheet shows the
3 tracks where YAMNet is most confident, with audio players that start just
before the frame where it peaked. You tick keep/drop and type the display
name; "Copy decisions" puts the result on the clipboard.

Tags use *peak* pooling (each class's highest frame score in the track).
Averaging over frames dilutes instruments that only play in part of a song:
at a 0.1 cutoff, mean pooling gave 3% of tracks 2-3 tags, peak pooling 52%.
Mood still uses mean pooling, which is what was evaluated.

    .venv/bin/python 03_tag_sheet.py
    open results/tag_sheet.html
"""

import csv
import html
import json
from collections import Counter, defaultdict

import numpy as np

from audio import load_windows_with_starts
from common import (
    DATA_DIR,
    RESULTS_DIR,
    TAG_GENRE_CLASSES,
    TAG_INSTRUMENT_BLOCK,
    TAG_INSTRUMENT_EXCLUDE,
    TAG_NAME_SUGGESTIONS,
    TAG_VOCAL_CLASSES,
    TRACKS_CSV,
)
from yamnet import HOP, YAMNET_SR, YamNet

CACHE = RESULTS_DIR / "yamnet_frame_scores.npz"
TAGS_PER_TRACK = 3
EXAMPLES_PER_CLASS = 3
PREVIEW_CUTOFF = 0.1  # only for the "clears 0.1" hint; strictness is undecided
LEAD_IN_SECONDS = 2.0


def frame_data(tracks: list[dict], yamnet: YamNet) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Per track: frame scores (n_frames, 521) and each frame's start time. Cached."""
    ids = [t["id"] for t in tracks]
    if CACHE.exists():
        cached = np.load(CACHE, allow_pickle=True)
        if list(cached["ids"]) == ids:
            return list(cached["scores"]), list(cached["times"])

    all_scores, all_times = [], []
    for i, track in enumerate(tracks):
        windows, starts = load_windows_with_starts(DATA_DIR / track["path"])
        per_window, _ = yamnet.frame_scores(windows)
        all_scores.append(np.concatenate(per_window).astype(np.float16))
        all_times.append(np.concatenate([
            start + np.arange(len(frames)) * HOP / YAMNET_SR
            for start, frames in zip(starts, per_window)
        ]))
        print(f"  {i + 1:>3}/{len(tracks)} {track['name'][:40]}")
    np.savez(CACHE, ids=np.array(ids),
             scores=np.array(all_scores, dtype=object), times=np.array(all_times, dtype=object))
    return all_scores, all_times


def candidates(class_names: list[str]) -> list[dict]:
    """(index, class, category, suggested display name) for every candidate."""
    out = [
        {"index": class_names.index(n), "name": n, "category": "Vocals", "suggestion": "vocals"}
        for n in TAG_VOCAL_CLASSES
    ]
    first, last = (class_names.index(n) for n in TAG_INSTRUMENT_BLOCK)
    for i in range(first, last + 1):
        name = class_names[i]
        if name not in TAG_INSTRUMENT_EXCLUDE:
            suggestion = TAG_NAME_SUGGESTIONS.get(name, name.lower())
            out.append({"index": i, "name": name, "category": "Instruments", "suggestion": suggestion})
    out += [
        {"index": class_names.index(n), "name": n, "category": "Genres", "suggestion": s}
        for n, s in TAG_GENRE_CLASSES.items()
    ]
    return out


def top_tag_counts(track_scores: np.ndarray, cands: list[dict]) -> tuple[Counter, dict]:
    """How often each class would be one of a track's top 3 tags.

    Classes sharing a display name (all vocal classes -> "vocals") compete as
    one tag, represented by their strongest member. No score threshold yet,
    so every track gets 3 tags; strictness is a later decision.
    """
    counts, tag_scores = Counter(), defaultdict(list)
    for scores in track_scores:
        best = {}
        for c in cands:
            s = float(scores[c["index"]])
            if c["suggestion"] not in best or s > best[c["suggestion"]][1]:
                best[c["suggestion"]] = (c["name"], s)
        top = sorted(best.values(), key=lambda x: x[1], reverse=True)[:TAGS_PER_TRACK]
        for name, s in top:
            counts[name] += 1
            tag_scores[name].append(s)
    return counts, tag_scores


def fmt_time(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def card(c: dict, count: int, scores: list[float], examples: list[dict]) -> str:
    clears = sum(s >= PREVIEW_CUTOFF for s in scores)
    rows = "".join(
        f"""<li>
          <audio controls preload="none" src="../data/tracks/{e['id']}.mp3#t={e['start']:.1f}"></audio>
          <div class="meta"><strong>{html.escape(e['track'])}</strong> · {html.escape(e['artist'])}
            <span class="dim">· peaks at {fmt_time(e['peak'])} · score {e['score']:.2f} ·
            <a href="{html.escape(e['url'])}" target="_blank" rel="noopener">Jamendo</a></span></div>
        </li>"""
        for e in examples
    )
    key = html.escape(c["name"])
    return f"""
    <section class="card" data-class="{key}">
      <header>
        <label class="keep"><input type="checkbox" checked> keep</label>
        <h3>{key}</h3>
        <input class="name" type="text" value="{html.escape(c['suggestion'])}" aria-label="Display name for {key}">
      </header>
      <p class="dim">A top-{TAGS_PER_TRACK} tag on <strong>{count}</strong> tracks;
        scores ≥ {PREVIEW_CUTOFF} on {clears} of them · typical score {np.median(scores):.2f} ·
        highest {max(scores):.2f}</p>
      <ol>{rows}</ol>
    </section>"""


def main() -> None:
    with TRACKS_CSV.open() as f:
        tracks = list(csv.DictReader(f))
    yamnet = YamNet()
    print(f"Scoring {len(tracks)} tracks frame by frame (cached after the first run) ...")
    frame_scores, frame_times = frame_data(tracks, yamnet)
    track_scores = np.stack([f.astype(np.float32).max(axis=0) for f in frame_scores])

    cands = candidates(yamnet.class_names)
    counts, tag_scores = top_tag_counts(track_scores, cands)

    sections, rare = defaultdict(list), []
    for c in sorted(cands, key=lambda c: -counts[c["name"]]):
        if counts[c["name"]] == 0:
            rare.append(c["name"])
            continue
        ranked = np.argsort(track_scores[:, c["index"]])[::-1][:EXAMPLES_PER_CLASS]
        examples = []
        for t in ranked:
            peak = float(frame_times[t][int(np.argmax(frame_scores[t][:, c["index"]]))])
            examples.append({
                "id": tracks[t]["id"], "track": tracks[t]["name"], "artist": tracks[t]["artist"],
                "url": tracks[t]["jamendo_url"], "peak": peak,
                "start": max(peak - LEAD_IN_SECONDS, 0.0),
                "score": float(track_scores[t, c["index"]]),
            })
        sections[c["category"]].append(card(c, counts[c["name"]], tag_scores[c["name"]], examples))

    body = "".join(
        f"<h2>{cat}</h2>" + "".join(sections[cat])
        for cat in ["Vocals", "Instruments", "Genres"] if sections[cat]
    )
    page = TEMPLATE.replace("{{BODY}}", body).replace("{{N}}", str(len(tracks)))
    page = page.replace("{{RARE}}", html.escape(", ".join(sorted(rare))) or "none")
    out = RESULTS_DIR / "tag_sheet.html"
    out.write_text(page)
    print(f"Wrote {out} ({sum(len(v) for v in sections.values())} classes, {len(rare)} never a top tag)")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sound Tag Sheet</title>
<style>
  :root { --bg: #fafaf9; --card: #fff; --fg: #1c1917; --dim: #78716c; --line: #e7e5e4; --accent: #4f46e5; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #0c0a09; --card: #1c1917; --fg: #f5f5f4; --dim: #a8a29e; --line: #292524; --accent: #a5b4fc; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, sans-serif; }
  main { max-width: 860px; margin: 0 auto; padding: 24px 16px 96px; }
  h1 { font-size: 24px; margin: 0 0 4px; }
  h2 { margin: 32px 0 12px; font-size: 18px; }
  .dim { color: var(--dim); }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; margin: 12px 0; }
  .card.dropped { opacity: .45; }
  .card header { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  .card h3 { margin: 0; font-size: 16px; flex: 1; min-width: 160px; }
  .card p { margin: 6px 0 8px; font-size: 13px; }
  .name { font: inherit; padding: 4px 8px; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); color: var(--fg); width: 180px; }
  .keep { font-size: 13px; white-space: nowrap; }
  ol { margin: 0; padding-left: 20px; }
  li { margin: 8px 0; }
  audio { width: 100%; max-width: 420px; height: 32px; }
  .meta { font-size: 13px; }
  a { color: var(--accent); }
  .bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--card); border-top: 1px solid var(--line); padding: 10px 16px; display: flex; gap: 8px; justify-content: center; }
  button { font: inherit; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); cursor: pointer; }
  button.primary { background: var(--accent); color: var(--bg); border-color: var(--accent); }
</style>
</head>
<body>
<main>
  <h1>Sound tag wording</h1>
  <p class="dim">Built from YAMNet scores on {{N}} Jamendo tracks. For each class: listen to the
  examples (each player starts 2 s before the moment YAMNet heard it most), untick <em>keep</em> if it's wrong or not
  worth saying, and edit the display name. Classes with the same display name merge into one tag.
  Your choices save in this browser as you go; use <strong>Copy decisions</strong> when done.</p>
  {{BODY}}
  <h2>Never a top-3 tag</h2>
  <p class="dim">{{RARE}}</p>
</main>
<div class="bar">
  <button class="primary" id="copy">Copy decisions</button>
  <button id="download">Download JSON</button>
</div>
<script>
  const KEY = "moodtune-tag-sheet";
  const cards = [...document.querySelectorAll(".card")];
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}

  function decisions() {
    const out = {};
    for (const c of cards) {
      out[c.dataset.class] = {
        keep: c.querySelector(".keep input").checked,
        name: c.querySelector(".name").value.trim(),
      };
    }
    return out;
  }
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(decisions())); } catch (e) {}
  }
  for (const c of cards) {
    const s = saved[c.dataset.class];
    const keep = c.querySelector(".keep input"), name = c.querySelector(".name");
    if (s) { keep.checked = s.keep; name.value = s.name; }
    c.classList.toggle("dropped", !keep.checked);
    keep.addEventListener("change", () => { c.classList.toggle("dropped", !keep.checked); persist(); });
    name.addEventListener("input", persist);
  }
  // One player at a time.
  document.addEventListener("play", e => {
    for (const a of document.querySelectorAll("audio")) if (a !== e.target) a.pause();
  }, true);

  const json = () => JSON.stringify(decisions(), null, 2);
  document.getElementById("copy").addEventListener("click", async e => {
    try { await navigator.clipboard.writeText(json()); e.target.textContent = "Copied"; }
    catch (err) { e.target.textContent = "Copy failed: use Download"; }
    setTimeout(() => (e.target.textContent = "Copy decisions"), 2000);
  });
  document.getElementById("download").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([json()], { type: "application/json" }));
    a.download = "tag_decisions.json";
    a.click();
  });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
