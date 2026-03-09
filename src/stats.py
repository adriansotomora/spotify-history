"""CLI query interface for Spotify play history."""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schema import DB_PATH


def get_conn(db_path=None):
    db = db_path or DB_PATH
    if not db.exists():
        print(f"ERROR: Database not found at {db}. Run collector.py first.")
        sys.exit(1)
    return sqlite3.connect(str(db))


def date_filter(days):
    if days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return f"AND p.played_at >= '{cutoff}'"
    return ""


def cmd_top_tracks(args):
    conn = get_conn()
    filt = date_filter(args.days)
    rows = conn.execute(f"""
        SELECT t.track_name, GROUP_CONCAT(DISTINCT a.artist_name) as artists,
               COUNT(*) as plays,
               ROUND(AVG(p.completion_pct) * 100, 1) as avg_pct,
               SUM(COALESCE(p.listened_ms, 0)) / 60000 as mins
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN track_artists ta ON t.track_id = ta.track_id
        JOIN artists a ON ta.artist_id = a.artist_id
        WHERE 1=1 {filt}
        GROUP BY p.track_id
        ORDER BY plays DESC
        LIMIT ?
    """, (args.limit,)).fetchall()

    period = f"last {args.days} days" if args.days else "all time"
    print(f"\nTop tracks ({period}):\n")
    for i, (name, artists, plays, avg_pct, mins) in enumerate(rows, 1):
        pct = f"{avg_pct}%" if avg_pct else "?"
        print(f"  {i:>3}. {name} — {artists}  ({plays} plays, {pct} avg completion, {mins:.0f} min)")
    conn.close()


def cmd_top_artists(args):
    conn = get_conn()
    filt = ""
    if args.days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
        filt = f"WHERE last_play >= '{cutoff}'"

    rows = conn.execute(f"""
        SELECT artist_name, total_plays, completed_plays, skipped_plays,
               total_listened_ms / 60000 as mins,
               ROUND(avg_completion_pct * 100, 1) as avg_pct
        FROM artist_summary
        {filt}
        ORDER BY total_plays DESC
        LIMIT ?
    """, (args.limit,)).fetchall()

    period = f"last {args.days} days" if args.days else "all time"
    print(f"\nTop artists ({period}):\n")
    for i, (name, total, completed, skipped, mins, avg_pct) in enumerate(rows, 1):
        pct = f"{avg_pct}%" if avg_pct else "?"
        print(f"  {i:>3}. {name}  ({total} plays, {skipped} skipped, {pct} avg, {mins:.0f} min)")
    conn.close()


def cmd_top_albums(args):
    conn = get_conn()
    filt = ""
    if args.days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
        filt = f"WHERE last_play >= '{cutoff}'"

    rows = conn.execute(f"""
        SELECT album_name, artist_names, total_plays,
               total_listened_ms / 60000 as mins,
               ROUND(avg_completion_pct * 100, 1) as avg_pct
        FROM album_summary
        {filt}
        ORDER BY total_plays DESC
        LIMIT ?
    """, (args.limit,)).fetchall()

    period = f"last {args.days} days" if args.days else "all time"
    print(f"\nTop albums ({period}):\n")
    for i, (album, artists, total, mins, avg_pct) in enumerate(rows, 1):
        pct = f"{avg_pct}%" if avg_pct else "?"
        print(f"  {i:>3}. {album} — {artists}  ({total} plays, {pct} avg, {mins:.0f} min)")
    conn.close()


def cmd_history(args):
    conn = get_conn()
    filt = date_filter(args.days)
    rows = conn.execute(f"""
        SELECT p.played_at, t.track_name,
               GROUP_CONCAT(DISTINCT a.artist_name) as artists,
               p.completion_pct, p.skipped
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN track_artists ta ON t.track_id = ta.track_id
        JOIN artists a ON ta.artist_id = a.artist_id
        WHERE 1=1 {filt}
        GROUP BY p.played_at
        ORDER BY p.played_at DESC
        LIMIT ?
    """, (args.limit,)).fetchall()

    print(f"\nRecent plays:\n")
    for played_at, name, artists, pct, skipped in rows:
        ts = played_at[:16].replace("T", " ")
        skip_flag = " [SKIP]" if skipped else ""
        pct_str = f"{pct * 100:.0f}%" if pct is not None else "..."
        print(f"  {ts}  {name} — {artists}  ({pct_str}){skip_flag}")
    conn.close()


def cmd_skipped(args):
    conn = get_conn()
    filt = date_filter(args.days)
    rows = conn.execute(f"""
        SELECT p.played_at, t.track_name,
               GROUP_CONCAT(DISTINCT a.artist_name) as artists,
               ROUND(p.completion_pct * 100, 1) as pct
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN track_artists ta ON t.track_id = ta.track_id
        JOIN artists a ON ta.artist_id = a.artist_id
        WHERE p.skipped = 1 {filt.replace('AND', 'AND')}
        GROUP BY p.played_at
        ORDER BY p.played_at DESC
        LIMIT ?
    """, (args.limit,)).fetchall()

    print(f"\nSkipped tracks ({len(rows)} shown):\n")
    for played_at, name, artists, pct in rows:
        ts = played_at[:16].replace("T", " ")
        print(f"  {ts}  {name} — {artists}  ({pct}% heard)")
    conn.close()


def cmd_track(args):
    conn = get_conn()
    query = f"%{args.name}%"
    rows = conn.execute("""
        SELECT t.track_name, GROUP_CONCAT(DISTINCT a.artist_name),
               COUNT(*) as plays,
               SUM(CASE WHEN p.skipped = 1 THEN 1 ELSE 0 END) as skips,
               ROUND(AVG(p.completion_pct) * 100, 1),
               SUM(COALESCE(p.listened_ms, 0)) / 60000,
               MIN(p.played_at), MAX(p.played_at)
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN track_artists ta ON t.track_id = ta.track_id
        JOIN artists a ON ta.artist_id = a.artist_id
        WHERE t.track_name LIKE ?
        GROUP BY p.track_id
        ORDER BY plays DESC
    """, (query,)).fetchall()

    if not rows:
        print(f"No tracks matching '{args.name}'")
        return

    for name, artists, plays, skips, avg_pct, mins, first, last in rows:
        print(f"\n  {name} — {artists}")
        print(f"  Plays: {plays} ({skips} skipped)")
        print(f"  Avg completion: {avg_pct}%")
        print(f"  Total listen time: {mins:.0f} min")
        print(f"  First: {first[:10]}  Last: {last[:10]}")
    conn.close()


def cmd_artist(args):
    conn = get_conn()
    query = f"%{args.name}%"
    rows = conn.execute("""
        SELECT artist_name, total_plays, completed_plays, skipped_plays,
               total_listened_ms / 60000,
               ROUND(avg_completion_pct * 100, 1),
               first_play, last_play
        FROM artist_summary
        WHERE artist_name LIKE ?
        ORDER BY total_plays DESC
    """, (query,)).fetchall()

    if not rows:
        print(f"No artists matching '{args.name}'")
        return

    for name, total, completed, skipped, mins, avg_pct, first, last in rows:
        print(f"\n  {name}")
        print(f"  Plays: {total} ({completed} completed, {skipped} skipped)")
        print(f"  Avg completion: {avg_pct}%")
        print(f"  Total listen time: {mins:.0f} min")
        print(f"  First: {first[:10]}  Last: {last[:10]}")
    conn.close()


def cmd_summary(args):
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    total_ms = conn.execute("SELECT SUM(COALESCE(listened_ms, 0)) FROM plays").fetchone()[0] or 0
    skips = conn.execute("SELECT COUNT(*) FROM plays WHERE skipped = 1").fetchone()[0]
    unique_tracks = conn.execute("SELECT COUNT(DISTINCT track_id) FROM plays").fetchone()[0]
    unique_artists = conn.execute("SELECT COUNT(DISTINCT artist_id) FROM track_artists WHERE track_id IN (SELECT DISTINCT track_id FROM plays)").fetchone()[0]
    date_range = conn.execute("SELECT MIN(played_at), MAX(played_at) FROM plays").fetchone()
    busiest = conn.execute("SELECT play_date, total_plays FROM daily_summary ORDER BY total_plays DESC LIMIT 1").fetchone()

    hours = total_ms / 3600000
    skip_rate = (skips / total * 100) if total > 0 else 0

    print(f"\n  Spotify Library Summary")
    print(f"  {'=' * 40}")
    print(f"  Total plays:      {total:,}")
    print(f"  Unique tracks:    {unique_tracks:,}")
    print(f"  Unique artists:   {unique_artists:,}")
    print(f"  Total listen time: {hours:.1f} hours")
    print(f"  Skip rate:        {skip_rate:.1f}%")
    if date_range[0]:
        print(f"  Date range:       {date_range[0][:10]} — {date_range[1][:10]}")
    if busiest:
        print(f"  Busiest day:      {busiest[0]} ({busiest[1]} plays)")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Spotify play history stats")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func in [("top-tracks", cmd_top_tracks), ("top-artists", cmd_top_artists), ("top-albums", cmd_top_albums)]:
        p = sub.add_parser(name)
        p.add_argument("--days", type=int, help="Filter to last N days")
        p.add_argument("--limit", type=int, default=20)
        p.set_defaults(func=func)

    for name, func in [("history", cmd_history), ("skipped", cmd_skipped)]:
        p = sub.add_parser(name)
        p.add_argument("--days", type=int, default=7)
        p.add_argument("--limit", type=int, default=50)
        p.set_defaults(func=func)

    for name, func, field in [("track", cmd_track, "name"), ("artist", cmd_artist, "name")]:
        p = sub.add_parser(name)
        p.add_argument(field)
        p.set_defaults(func=func)

    p = sub.add_parser("summary")
    p.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
