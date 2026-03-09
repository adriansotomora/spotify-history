"""Database schema initialization for the medallion architecture."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "spotify.db"

BRONZE_TABLES = """
CREATE TABLE IF NOT EXISTS raw_plays (
    played_at TEXT PRIMARY KEY,
    track_id TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);
"""

SILVER_TABLES = """
CREATE TABLE IF NOT EXISTS tracks (
    track_id TEXT PRIMARY KEY,
    track_name TEXT NOT NULL,
    album_id TEXT,
    album_name TEXT,
    duration_ms INTEGER,
    track_uri TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS artists (
    artist_id TEXT PRIMARY KEY,
    artist_name TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS track_artists (
    track_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    artist_order INTEGER DEFAULT 0,
    PRIMARY KEY (track_id, artist_id)
);

CREATE TABLE IF NOT EXISTS plays (
    played_at TEXT PRIMARY KEY,
    track_id TEXT NOT NULL,
    listened_ms INTEGER,
    completion_pct REAL,
    skipped INTEGER,
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

CREATE INDEX IF NOT EXISTS idx_plays_track_id ON plays(track_id);
CREATE INDEX IF NOT EXISTS idx_plays_played_at ON plays(played_at);
CREATE INDEX IF NOT EXISTS idx_track_artists_artist ON track_artists(artist_id);
"""

GOLD_TABLES = """
CREATE TABLE IF NOT EXISTS artist_summary (
    artist_id TEXT PRIMARY KEY,
    artist_name TEXT,
    total_plays INTEGER,
    completed_plays INTEGER,
    skipped_plays INTEGER,
    total_listened_ms INTEGER,
    avg_completion_pct REAL,
    first_play TEXT,
    last_play TEXT
);

CREATE TABLE IF NOT EXISTS album_summary (
    album_id TEXT PRIMARY KEY,
    album_name TEXT,
    artist_names TEXT,
    total_plays INTEGER,
    completed_plays INTEGER,
    skipped_plays INTEGER,
    total_listened_ms INTEGER,
    avg_completion_pct REAL,
    first_play TEXT,
    last_play TEXT
);

CREATE TABLE IF NOT EXISTS daily_summary (
    play_date TEXT PRIMARY KEY,
    total_plays INTEGER,
    unique_tracks INTEGER,
    unique_artists INTEGER,
    total_listened_ms INTEGER,
    skip_rate REAL,
    top_artist TEXT,
    top_track TEXT
);
"""


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Create all tables and return a connection with WAL mode enabled."""
    db = db_path or DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(BRONZE_TABLES)
    conn.executescript(SILVER_TABLES)
    conn.executescript(GOLD_TABLES)
    conn.commit()
    return conn


if __name__ == "__main__":
    conn = init_db()
    print(f"Database initialized at {DB_PATH}")
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for (t,) in tables:
        print(f"  - {t}")
    conn.close()
