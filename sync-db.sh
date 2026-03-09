#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_DB="$SCRIPT_DIR/data/spotify.db"

# Configure your EC2 host here (or pass as argument)
EC2_HOST="${1:-${SPOTIFY_EC2_HOST:-}}"

if [ -z "$EC2_HOST" ]; then
    echo "Usage: bash sync-db.sh user@ec2-host"
    echo "   or: export SPOTIFY_EC2_HOST=user@ec2-host"
    exit 1
fi

REMOTE_DB="~/spotify-history/data/spotify.db"

echo "Syncing database from $EC2_HOST..."
mkdir -p "$SCRIPT_DIR/data"
scp "$EC2_HOST:$REMOTE_DB" "$LOCAL_DB"

SIZE=$(du -h "$LOCAL_DB" | cut -f1)
PLAYS=$(sqlite3 "$LOCAL_DB" "SELECT COUNT(*) FROM plays" 2>/dev/null || echo "?")
LATEST=$(sqlite3 "$LOCAL_DB" "SELECT MAX(played_at) FROM plays" 2>/dev/null || echo "?")

echo "Synced: $SIZE ($PLAYS plays, latest: ${LATEST:0:16})"
echo ""

read -p "Launch dashboard? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    cd "$SCRIPT_DIR"
    .venv/bin/streamlit run src/dashboard.py
fi
