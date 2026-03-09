"""Streamlit dashboard for Spotify listening history."""

import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "spotify.db"


def get_conn():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def run_sync_pipeline():
    """Run collector on EC2, then SCP the database to local."""
    from ec2_config import EC2_HOST, PEM_PATH, REMOTE_PROJECT

    ssh_opts = ["-i", str(PEM_PATH), "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
    steps = []

    # Step 1: Run collector on EC2
    steps.append(("Collecting plays from Spotify on EC2...", [
        "ssh", *ssh_opts, EC2_HOST,
        f"cd {REMOTE_PROJECT} && .venv/bin/python src/collector.py"
    ]))

    # Step 2: SCP database to local
    steps.append(("Syncing database to Mac...", [
        "scp", *ssh_opts,
        f"{EC2_HOST}:{REMOTE_PROJECT}/data/spotify.db",
        str(DB_PATH)
    ]))

    results = []
    for label, cmd in steps:
        yield label, None
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = result.stdout.strip() or result.stderr.strip()
            if result.returncode != 0:
                yield label, f"ERROR: {output}"
                return
            results.append(output)
            yield label, output
        except subprocess.TimeoutExpired:
            yield label, "ERROR: Command timed out (60s)"
            return
        except Exception as e:
            yield label, f"ERROR: {e}"
            return

    yield "Done!", "\n".join(results)


def db_last_modified():
    if DB_PATH.exists():
        return datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return None


# --- Page config ---
st.set_page_config(page_title="Spotify History", page_icon="🎵", layout="wide")

# --- Header with sync button ---
header_left, header_right = st.columns([3, 1])
with header_left:
    st.title("Spotify Listening History")
with header_right:
    st.write("")
    last_mod = db_last_modified()
    if last_mod:
        st.caption(f"DB synced: {last_mod}")
    if st.button("🔄 Refresh from EC2", use_container_width=True, type="primary"):
        progress = st.empty()
        status_log = st.empty()
        messages = []
        for label, output in run_sync_pipeline():
            if output is None:
                progress.info(f"⏳ {label}")
            elif output.startswith("ERROR"):
                progress.error(f"❌ {label}")
                status_log.code(output)
                st.stop()
            else:
                messages.append(f"✅ {label}")
                if output:
                    messages.append(f"   {output}")

        progress.success("Pipeline complete!")
        status_log.code("\n".join(messages))
        time.sleep(1.5)
        st.rerun()


if not DB_PATH.exists():
    st.warning("No database found. Click **Refresh from EC2** to sync.")
    st.stop()

conn = get_conn()

# --- Summary metrics ---
col1, col2, col3, col4, col5 = st.columns(5)
total_plays = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
total_hours = (conn.execute("SELECT SUM(COALESCE(listened_ms, 0)) FROM plays").fetchone()[0] or 0) / 3600000
unique_tracks = conn.execute("SELECT COUNT(DISTINCT track_id) FROM plays").fetchone()[0]
unique_artists = conn.execute("SELECT COUNT(*) FROM artist_summary").fetchone()[0]
skip_rate = conn.execute(
    "SELECT ROUND(CAST(SUM(CASE WHEN skipped=1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) * 100, 1) FROM plays"
).fetchone()[0] or 0

col1.metric("Total Plays", f"{total_plays:,}")
col2.metric("Hours Listened", f"{total_hours:.1f}")
col3.metric("Unique Tracks", f"{unique_tracks:,}")
col4.metric("Unique Artists", f"{unique_artists:,}")
col5.metric("Skip Rate", f"{skip_rate}%")

st.divider()

# --- Tabs ---
tab_overview, tab_artists, tab_albums, tab_tracks, tab_history = st.tabs(
    ["Overview", "Artists", "Albums", "Tracks", "History"]
)

# --- Overview tab ---
with tab_overview:
    daily = pd.read_sql_query("SELECT * FROM daily_summary ORDER BY play_date", conn)
    if not daily.empty:
        daily["hours"] = daily["total_listened_ms"] / 3600000

        st.subheader("Listening Over Time")
        fig = px.bar(daily, x="play_date", y="hours",
                     hover_data=["total_plays", "unique_tracks", "top_artist"],
                     labels={"play_date": "Date", "hours": "Hours"})
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)

        ov_left, ov_right = st.columns(2)
        with ov_left:
            st.subheader("Plays per Day")
            fig = px.bar(daily, x="play_date", y="total_plays",
                         labels={"play_date": "Date", "total_plays": "Plays"})
            fig.update_layout(showlegend=False, height=250)
            st.plotly_chart(fig, use_container_width=True)

        with ov_right:
            st.subheader("Skip Rate Trend")
            fig = px.line(daily, x="play_date", y="skip_rate",
                          labels={"play_date": "Date", "skip_rate": "Skip Rate"})
            fig.update_layout(height=250, yaxis_tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)

# --- Artists tab ---
with tab_artists:
    limit = st.slider("Show top N artists", 5, 50, 20, key="artist_limit")
    artists = pd.read_sql_query(
        f"SELECT artist_name, total_plays, completed_plays, skipped_plays, "
        f"total_listened_ms / 60000 as minutes, "
        f"ROUND(avg_completion_pct * 100, 1) as completion "
        f"FROM artist_summary ORDER BY total_plays DESC LIMIT {limit}",
        conn,
    )
    if not artists.empty:
        fig = px.bar(artists, x="total_plays", y="artist_name", orientation="h",
                     color="completion", color_continuous_scale="RdYlGn", range_color=[50, 100],
                     hover_data=["completed_plays", "skipped_plays", "minutes"],
                     labels={"total_plays": "Plays", "artist_name": ""})
        fig.update_layout(yaxis=dict(autorange="reversed"), height=max(400, limit * 28),
                          coloraxis_colorbar_title="Completion %")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Artist Details")
        display = artists.copy()
        display.columns = ["Artist", "Plays", "Completed", "Skipped", "Minutes", "Completion %"]
        st.dataframe(display, use_container_width=True, hide_index=True)

# --- Albums tab ---
with tab_albums:
    limit = st.slider("Show top N albums", 5, 50, 20, key="album_limit")
    albums = pd.read_sql_query(
        f"SELECT album_name, artist_names, total_plays, "
        f"total_listened_ms / 60000 as minutes, "
        f"ROUND(avg_completion_pct * 100, 1) as completion "
        f"FROM album_summary ORDER BY total_plays DESC LIMIT {limit}",
        conn,
    )
    if not albums.empty:
        albums["label"] = albums["album_name"] + " — " + albums["artist_names"].fillna("")
        fig = px.bar(albums, x="total_plays", y="label", orientation="h",
                     color="completion", color_continuous_scale="RdYlGn", range_color=[50, 100],
                     hover_data=["minutes"],
                     labels={"total_plays": "Plays", "label": ""})
        fig.update_layout(yaxis=dict(autorange="reversed"), height=max(400, limit * 28),
                          coloraxis_colorbar_title="Completion %")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Album Details")
        display = albums[["album_name", "artist_names", "total_plays", "minutes", "completion"]].copy()
        display.columns = ["Album", "Artists", "Plays", "Minutes", "Completion %"]
        st.dataframe(display, use_container_width=True, hide_index=True)

# --- Tracks tab ---
with tab_tracks:
    search = st.text_input("Search tracks", placeholder="Filter by track name...")
    limit = st.slider("Show top N tracks", 10, 100, 30, key="track_limit")

    where = f"WHERE t.track_name LIKE '%{search}%'" if search else ""
    tracks = pd.read_sql_query(f"""
        SELECT t.track_name, GROUP_CONCAT(DISTINCT a.artist_name) as artists,
               t.album_name,
               COUNT(*) as plays,
               SUM(CASE WHEN p.skipped = 1 THEN 1 ELSE 0 END) as skips,
               ROUND(AVG(p.completion_pct) * 100, 1) as completion,
               SUM(COALESCE(p.listened_ms, 0)) / 60000 as minutes
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN track_artists ta ON t.track_id = ta.track_id
        JOIN artists a ON ta.artist_id = a.artist_id
        {where}
        GROUP BY p.track_id
        ORDER BY plays DESC
        LIMIT {limit}
    """, conn)

    if not tracks.empty:
        fig = px.bar(tracks, x="plays", y="track_name", orientation="h",
                     color="completion", color_continuous_scale="RdYlGn", range_color=[50, 100],
                     hover_data=["artists", "album_name", "skips", "minutes"],
                     labels={"plays": "Plays", "track_name": ""})
        fig.update_layout(yaxis=dict(autorange="reversed"), height=max(400, len(tracks) * 28),
                          coloraxis_colorbar_title="Completion %")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Track Details")
        display = tracks.copy()
        display.columns = ["Track", "Artists", "Album", "Plays", "Skips", "Completion %", "Minutes"]
        st.dataframe(display, use_container_width=True, hide_index=True)
    elif search:
        st.info(f"No tracks matching '{search}'")

# --- History tab ---
with tab_history:
    days_filter = st.slider("Last N days", 1, 90, 7, key="history_days")
    show_skipped_only = st.checkbox("Show skipped only")

    skip_clause = "AND p.skipped = 1" if show_skipped_only else ""
    history = pd.read_sql_query(f"""
        SELECT p.played_at, t.track_name as track,
               GROUP_CONCAT(DISTINCT a.artist_name) as artist,
               t.album_name as album,
               ROUND(p.completion_pct * 100) as completion,
               CASE WHEN p.skipped = 1 THEN 'Skipped' ELSE 'Played' END as status
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN track_artists ta ON t.track_id = ta.track_id
        JOIN artists a ON ta.artist_id = a.artist_id
        WHERE p.played_at >= datetime('now', '-{days_filter} days')
        {skip_clause}
        GROUP BY p.played_at
        ORDER BY p.played_at DESC
    """, conn)

    if not history.empty:
        history["played_at"] = pd.to_datetime(history["played_at"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True,
            column_config={
                "played_at": st.column_config.TextColumn("Time"),
                "track": "Track",
                "artist": "Artist",
                "album": "Album",
                "completion": st.column_config.NumberColumn("Completion %", format="%d%%"),
                "status": "Status",
            },
        )
        st.caption(f"{len(history)} plays shown")
    else:
        st.info("No plays in this period.")

conn.close()
