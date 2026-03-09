"""Collector: fetch recently-played from Spotify and insert into bronze layer."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth import get_spotify_client
from schema import DB_PATH, init_db
from pipeline import run_pipeline


def collect(db_path=None):
    """Fetch recent plays and insert new ones into raw_plays (bronze)."""
    sp = get_spotify_client()
    conn = init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()

    results = sp.current_user_recently_played(limit=50)
    items = results.get("items", [])

    if not items:
        conn.close()
        return 0

    new_count = 0
    for item in items:
        played_at = item["played_at"]
        track = item["track"]

        existing = conn.execute(
            "SELECT 1 FROM raw_plays WHERE played_at = ?", (played_at,)
        ).fetchone()

        if existing:
            continue

        conn.execute(
            "INSERT INTO raw_plays (played_at, track_id, raw_json, ingested_at) VALUES (?, ?, ?, ?)",
            (played_at, track["id"], json.dumps(item), now),
        )
        new_count += 1

    conn.commit()
    conn.close()
    return new_count


def main():
    new = collect()
    if new > 0:
        print(f"Collected {new} new play(s).")
        run_pipeline()
    else:
        print("No new plays.")


if __name__ == "__main__":
    main()
