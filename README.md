# Spotify Listening History

Track your Spotify play history with a medallion-architecture SQLite database, CLI stats, and a Streamlit dashboard.

## Architecture

```
Spotify API  -->  collector.py  -->  [Bronze: raw_plays]
                                          |
                                    pipeline.py
                                          |
                             [Silver: plays, tracks, artists]
                                          |
                             [Gold: artist_summary, album_summary, daily_summary]
                                          |
                            stats.py (CLI)  |  dashboard.py (Web)
```

## Quick Start

```bash
# Clone
git clone https://github.com/adriansotomora/spotify-library.git
cd spotify-library

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Spotify app credentials

# First-time auth (opens browser)
python src/auth.py

# Collect plays
python src/collector.py

# View stats
python src/stats.py summary
python src/stats.py top-tracks --days 7
python src/stats.py top-artists --limit 10
python src/stats.py history
python src/stats.py skipped
python src/stats.py track "Song Name"
python src/stats.py artist "Artist Name"

# Dashboard
streamlit run src/dashboard.py
```

## EC2 Deployment

```bash
# On your EC2 instance:
git clone https://github.com/adriansotomora/spotify-library.git
cd spotify-library
bash setup.sh
```

This installs systemd services for:
- **Collector timer**: runs every 30 minutes
- **Dashboard**: Streamlit on port 8501

## Stats CLI Commands

| Command | Description |
|---------|-------------|
| `summary` | Overall library statistics |
| `top-tracks [--days N] [--limit N]` | Most played tracks |
| `top-artists [--days N] [--limit N]` | Most played artists |
| `top-albums [--days N] [--limit N]` | Most played albums |
| `history [--days N] [--limit N]` | Recent play log |
| `skipped [--days N] [--limit N]` | Skipped tracks |
| `track "name"` | Detailed stats for a track |
| `artist "name"` | Detailed stats for an artist |

## Skip Detection

The pipeline infers skips by comparing the time gap between consecutive plays with each track's duration. A play with < 80% completion is flagged as skipped.
