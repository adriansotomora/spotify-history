"""ETL pipeline: bronze -> silver -> gold with skip detection."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from schema import DB_PATH, init_db


def bronze_to_silver(conn):
    """Parse raw_plays into normalized silver tables."""
    now = datetime.now(timezone.utc).isoformat()

    unprocessed = conn.execute("""
        SELECT r.played_at, r.raw_json
        FROM raw_plays r
        LEFT JOIN plays p ON r.played_at = p.played_at
        WHERE p.played_at IS NULL
        ORDER BY r.played_at
    """).fetchall()

    for played_at, raw_json in unprocessed:
        item = json.loads(raw_json)
        track = item["track"]
        album = track.get("album", {})

        conn.execute("""
            INSERT OR REPLACE INTO tracks (track_id, track_name, album_id, album_name, duration_ms, track_uri, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            track["id"],
            track["name"],
            album.get("id"),
            album.get("name"),
            track.get("duration_ms"),
            track.get("uri"),
            now,
        ))

        for i, artist in enumerate(track.get("artists", [])):
            conn.execute("""
                INSERT OR REPLACE INTO artists (artist_id, artist_name, updated_at)
                VALUES (?, ?, ?)
            """, (artist["id"], artist["name"], now))

            conn.execute("""
                INSERT OR IGNORE INTO track_artists (track_id, artist_id, artist_order)
                VALUES (?, ?, ?)
            """, (track["id"], artist["id"], i))

        conn.execute("""
            INSERT OR IGNORE INTO plays (played_at, track_id)
            VALUES (?, ?)
        """, (played_at, track["id"]))

    conn.commit()


def backfill_skip_detection(conn):
    """Calculate listened_ms and completion for plays missing this data."""
    pending = conn.execute("""
        SELECT p.played_at, p.track_id, t.duration_ms
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        WHERE p.listened_ms IS NULL
        ORDER BY p.played_at
    """).fetchall()

    for i, (played_at, track_id, duration_ms) in enumerate(pending):
        next_row = conn.execute("""
            SELECT played_at FROM plays
            WHERE played_at > ?
            ORDER BY played_at ASC
            LIMIT 1
        """, (played_at,)).fetchone()

        if not next_row:
            continue

        from datetime import datetime
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        try:
            t1 = datetime.strptime(played_at, fmt)
            t2 = datetime.strptime(next_row[0], fmt)
        except ValueError:
            t1 = datetime.fromisoformat(played_at.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(next_row[0].replace("Z", "+00:00"))

        gap_ms = int((t2 - t1).total_seconds() * 1000)
        listened_ms = min(gap_ms, duration_ms * 2) if duration_ms else gap_ms
        completion = min(listened_ms / duration_ms, 1.0) if duration_ms and duration_ms > 0 else None
        skipped = 1 if completion is not None and completion < 0.6 else 0

        conn.execute("""
            UPDATE plays SET listened_ms = ?, completion_pct = ?, skipped = ?
            WHERE played_at = ?
        """, (listened_ms, completion, skipped, played_at))

    conn.commit()


def silver_to_gold(conn):
    """Rebuild gold summary tables from silver data."""
    conn.execute("DELETE FROM artist_summary")
    conn.execute("""
        INSERT INTO artist_summary
        SELECT
            a.artist_id,
            a.artist_name,
            COUNT(*) as total_plays,
            SUM(CASE WHEN p.skipped = 0 THEN 1 ELSE 0 END) as completed_plays,
            SUM(CASE WHEN p.skipped = 1 THEN 1 ELSE 0 END) as skipped_plays,
            SUM(COALESCE(p.listened_ms, 0)) as total_listened_ms,
            AVG(p.completion_pct) as avg_completion_pct,
            MIN(p.played_at) as first_play,
            MAX(p.played_at) as last_play
        FROM plays p
        JOIN track_artists ta ON p.track_id = ta.track_id
        JOIN artists a ON ta.artist_id = a.artist_id
        GROUP BY a.artist_id, a.artist_name
    """)

    conn.execute("DELETE FROM album_summary")
    conn.execute("""
        INSERT INTO album_summary
        SELECT
            t.album_id,
            t.album_name,
            GROUP_CONCAT(DISTINCT ar.artist_name) as artist_names,
            COUNT(*) as total_plays,
            SUM(CASE WHEN p.skipped = 0 THEN 1 ELSE 0 END) as completed_plays,
            SUM(CASE WHEN p.skipped = 1 THEN 1 ELSE 0 END) as skipped_plays,
            SUM(COALESCE(p.listened_ms, 0)) as total_listened_ms,
            AVG(p.completion_pct) as avg_completion_pct,
            MIN(p.played_at) as first_play,
            MAX(p.played_at) as last_play
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN track_artists ta ON t.track_id = ta.track_id
        JOIN artists ar ON ta.artist_id = ar.artist_id
        GROUP BY t.album_id, t.album_name
    """)

    conn.execute("DELETE FROM daily_summary")
    conn.execute("""
        INSERT INTO daily_summary
        SELECT
            DATE(p.played_at) as play_date,
            COUNT(*) as total_plays,
            COUNT(DISTINCT p.track_id) as unique_tracks,
            COUNT(DISTINCT ta.artist_id) as unique_artists,
            SUM(COALESCE(p.listened_ms, 0)) as total_listened_ms,
            ROUND(CAST(SUM(CASE WHEN p.skipped = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 3) as skip_rate,
            (SELECT ar2.artist_name
             FROM plays p2
             JOIN track_artists ta2 ON p2.track_id = ta2.track_id
             JOIN artists ar2 ON ta2.artist_id = ar2.artist_id
             WHERE DATE(p2.played_at) = DATE(p.played_at)
             GROUP BY ar2.artist_name
             ORDER BY COUNT(*) DESC LIMIT 1) as top_artist,
            (SELECT t2.track_name
             FROM plays p2
             JOIN tracks t2 ON p2.track_id = t2.track_id
             WHERE DATE(p2.played_at) = DATE(p.played_at)
             GROUP BY t2.track_name
             ORDER BY COUNT(*) DESC LIMIT 1) as top_track
        FROM plays p
        JOIN track_artists ta ON p.track_id = ta.track_id
        GROUP BY DATE(p.played_at)
    """)

    conn.commit()


def run_pipeline(db_path=None):
    """Run the full ETL pipeline."""
    conn = init_db(db_path)
    bronze_to_silver(conn)
    backfill_skip_detection(conn)
    silver_to_gold(conn)
    conn.close()
    print("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
