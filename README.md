# Spotify Listening History

Track your Spotify play history with a medallion-architecture SQLite database, CLI stats, and a Streamlit dashboard.

## Architecture

```
EC2 (always-on):
  Spotify API  -->  collector.py (every 15 min)  -->  [Bronze: raw_plays]
                                                            |
                                                      pipeline.py
                                                            |
                                               [Silver: plays, tracks, artists]
                                                            |
                                               [Gold: summaries]  -->  spotify.db

Local Mac (on-demand):
  scp spotify.db  -->  stats.py (CLI)
                  -->  dashboard.py (Streamlit)
```

## Quick Start (Local)

```bash
git clone https://github.com/adriansotomora/spotify-history.git
cd spotify-history

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Spotify app credentials

# First-time auth (opens browser)
python src/auth.py

# Collect plays manually
python src/collector.py

# View stats
python src/stats.py summary
python src/stats.py top-tracks --days 7
python src/stats.py top-artists --limit 10
python src/stats.py history
python src/stats.py skipped
python src/stats.py track "Song Name"
python src/stats.py artist "Artist Name"
```

## EC2 Deployment (Collector Only)

The EC2 instance runs the collector every 15 minutes. No dashboard, no open ports needed.

```bash
# On your EC2 instance:
git clone https://github.com/adriansotomora/spotify-history.git
cd spotify-history
bash setup.sh
```

Copy your token cache from your Mac:
```bash
scp .spotify_token_cache user@ec2-host:~/spotify-history/
```

## Local Dashboard

Sync the database from EC2 and launch the dashboard on your Mac:

```bash
bash sync-db.sh user@ec2-host
```

Or set the host once and forget:
```bash
export SPOTIFY_EC2_HOST=user@ec2-host
bash sync-db.sh
```

This copies the DB (~5MB) and opens Streamlit locally.

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
