"""Step 1: download a small, mood-labelled test set from Jamendo.

Jamendo tracks are Creative Commons and carry free-form mood tags
("vartags"). Those tags are noisy, so we only keep tracks whose tags point
at exactly one of the app's 4 mood buckets. The tags become our (rough)
ground truth.

    .venv/bin/python 01_fetch_tracks.py --per-bucket 10
"""

import argparse
import csv
import time

import httpx

from common import (
    APP_ENV,
    BUCKET_QUERIES,
    BUCKET_TAGS,
    BUCKETS,
    DATA_DIR,
    TRACKS_CSV,
    TRACKS_DIR,
)

API = "https://api.jamendo.com/v3.0/tracks/"


def client_id() -> str:
    for line in APP_ENV.read_text().splitlines():
        if line.startswith("JAMENDO_CLIENT_ID="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit(f"JAMENDO_CLIENT_ID not found in {APP_ENV}")


def buckets_for(vartags: list[str]) -> set[str]:
    tags = {t.lower() for t in vartags}
    return {b for b, words in BUCKET_TAGS.items() if tags & words}


def search(http: httpx.Client, cid: str, query: dict) -> list[dict]:
    """Jamendo sometimes returns an empty page for a valid query; retry."""
    params = {
        "client_id": cid,
        "format": "json",
        "limit": 200,
        "include": "musicinfo",
        "order": "popularity_total",
        "audioformat": "mp32",
        **query,
    }
    for attempt in range(3):
        results = http.get(API, params=params).raise_for_status().json()["results"]
        if results:
            return results
        time.sleep(1 + attempt)
    return []


def download(http: httpx.Client, track: dict) -> bool:
    """Saves the mp3; some stream URLs 404, so callers skip those tracks."""
    path = TRACKS_DIR / f"{track['id']}.mp3"
    if path.exists():
        return True
    response = http.get(track["audio"])
    if response.status_code != 200:
        print(f"  skip {track['id']} ({response.status_code})")
        return False
    path.write_bytes(response.content)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-bucket", type=int, default=10)
    args = parser.parse_args()

    cid = client_id()
    TRACKS_DIR.mkdir(parents=True, exist_ok=True)
    chosen: dict[str, list[dict]] = {b: [] for b in BUCKETS}
    seen: set[str] = set()

    with httpx.Client(timeout=60, follow_redirects=True) as http:
        for bucket in BUCKETS:
            for query in BUCKET_QUERIES[bucket]:
                for track in search(http, cid, query):
                    if len(chosen[bucket]) >= args.per_bucket:
                        break
                    vartags = track["musicinfo"]["tags"]["vartags"]
                    if track["id"] in seen or "podcast" in vartags:
                        continue
                    if not 60 <= track["duration"] <= 480 or not track["audio"]:
                        continue
                    if buckets_for(vartags) != {bucket}:
                        continue  # ambiguous or off-bucket tags
                    seen.add(track["id"])
                    if download(http, track):
                        chosen[bucket].append(track)
            print(f"{bucket:<11} {len(chosen[bucket])} tracks")

        rows = []
        for bucket, tracks in chosen.items():
            for track in tracks:
                path = TRACKS_DIR / f"{track['id']}.mp3"
                rows.append({
                    "id": track["id"],
                    "name": track["name"],
                    "artist": track["artist_name"],
                    "bucket": bucket,
                    "vartags": "|".join(track["musicinfo"]["tags"]["vartags"]),
                    "genres": "|".join(track["musicinfo"]["tags"]["genres"]),
                    "duration": track["duration"],
                    "path": str(path.relative_to(DATA_DIR)),
                    "jamendo_url": track["shareurl"],
                })

    with TRACKS_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} tracks to {TRACKS_CSV}")


if __name__ == "__main__":
    main()
