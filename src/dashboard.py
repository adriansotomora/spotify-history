"""Streamlit dashboard for Spotify listening history."""

import sqlite3
from pathlib import Path

import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "data" / "spotify.db"


@st.cache_resource
def get_conn():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def load_table(conn, table, limit=None):
    query = f"SELECT * FROM {table}"
    if limit:
        query += f" LIMIT {limit}"
    import pandas as pd
    return pd.read_sql_query(query, conn)


st.set_page_config(page_title="Spotify Library", page_icon="🎵", layout="wide")
st.title("Spotify Listening History")

if not DB_PATH.exists():
    st.error("Database not found. Run the collector first.")
    st.stop()

conn = get_conn()

# Summary metrics
col1, col2, col3, col4 = st.columns(4)
total_plays = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
total_hours = (conn.execute("SELECT SUM(COALESCE(listened_ms, 0)) FROM plays").fetchone()[0] or 0) / 3600000
unique_artists = conn.execute("SELECT COUNT(*) FROM artist_summary").fetchone()[0]
skip_rate = conn.execute("SELECT ROUND(CAST(SUM(CASE WHEN skipped=1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) * 100, 1) FROM plays").fetchone()[0] or 0

col1.metric("Total Plays", f"{total_plays:,}")
col2.metric("Hours Listened", f"{total_hours:.1f}")
col3.metric("Unique Artists", f"{unique_artists:,}")
col4.metric("Skip Rate", f"{skip_rate}%")

st.divider()

# Daily listening
import pandas as pd

daily = pd.read_sql_query("SELECT * FROM daily_summary ORDER BY play_date", conn)
if not daily.empty:
    st.subheader("Listening Over Time")
    daily["hours"] = daily["total_listened_ms"] / 3600000
    fig = px.bar(daily, x="play_date", y="hours", labels={"play_date": "Date", "hours": "Hours"})
    fig.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig, use_container_width=True)

# Top artists and albums side by side
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Top Artists")
    artists = pd.read_sql_query(
        "SELECT artist_name, total_plays, ROUND(avg_completion_pct * 100, 1) as completion FROM artist_summary ORDER BY total_plays DESC LIMIT 15",
        conn,
    )
    if not artists.empty:
        fig = px.bar(artists, x="total_plays", y="artist_name", orientation="h",
                     labels={"total_plays": "Plays", "artist_name": ""},
                     color="completion", color_continuous_scale="RdYlGn", range_color=[50, 100])
        fig.update_layout(yaxis=dict(autorange="reversed"), height=450, coloraxis_colorbar_title="Completion %")
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Top Albums")
    albums = pd.read_sql_query(
        "SELECT album_name, artist_names, total_plays FROM album_summary ORDER BY total_plays DESC LIMIT 15",
        conn,
    )
    if not albums.empty:
        albums["label"] = albums["album_name"] + " — " + albums["artist_names"]
        fig = px.bar(albums, x="total_plays", y="label", orientation="h",
                     labels={"total_plays": "Plays", "label": ""})
        fig.update_layout(yaxis=dict(autorange="reversed"), height=450, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# Skip rate trend
if not daily.empty and "skip_rate" in daily.columns:
    st.subheader("Skip Rate Trend")
    fig = px.line(daily, x="play_date", y="skip_rate",
                  labels={"play_date": "Date", "skip_rate": "Skip Rate"})
    fig.update_layout(height=250, yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

# Recent plays
st.subheader("Recent Plays")
recent = pd.read_sql_query("""
    SELECT p.played_at, t.track_name as Track, GROUP_CONCAT(DISTINCT a.artist_name) as Artist,
           t.album_name as Album,
           ROUND(p.completion_pct * 100) as "Completion %",
           CASE WHEN p.skipped = 1 THEN 'Skipped' ELSE 'Completed' END as Status
    FROM plays p
    JOIN tracks t ON p.track_id = t.track_id
    JOIN track_artists ta ON t.track_id = ta.track_id
    JOIN artists a ON ta.artist_id = a.artist_id
    GROUP BY p.played_at
    ORDER BY p.played_at DESC
    LIMIT 50
""", conn)

if not recent.empty:
    recent["played_at"] = pd.to_datetime(recent["played_at"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(recent, use_container_width=True, hide_index=True)
