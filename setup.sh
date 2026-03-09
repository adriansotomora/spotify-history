#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== Spotify Library - EC2 Setup ==="

# Install system deps if needed
if ! command -v python3 &>/dev/null; then
    echo "Installing Python..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv git
    elif command -v yum &>/dev/null; then
        sudo yum install -y python3 python3-pip git
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-pip git
    fi
fi

# Create venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing dependencies (collector only, no dashboard deps)..."
.venv/bin/pip install -q spotipy python-dotenv

# .env setup
if [ ! -f ".env" ]; then
    echo ""
    echo "No .env file found. Let's set up your Spotify credentials."
    read -p "Spotify Client ID: " client_id
    read -p "Spotify Client Secret: " client_secret
    cat > .env <<EOF
SPOTIFY_CLIENT_ID=$client_id
SPOTIFY_CLIENT_SECRET=$client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
EOF
    chmod 600 .env
    echo "Credentials saved to .env"
fi

# Token cache check
if [ ! -f ".spotify_token_cache" ]; then
    echo ""
    echo "WARNING: No token cache found."
    echo "Copy it from your local machine:"
    echo "  scp ~/.config/spotify-skill/.spotify_token_cache EC2_HOST:$PROJECT_DIR/.spotify_token_cache"
    echo ""
    echo "Or run: .venv/bin/python src/auth.py"
    echo "(This requires a browser for first-time OAuth)"
fi

# Create data dir
mkdir -p data

# Install systemd units
echo ""
echo "Installing systemd services..."

sudo tee /etc/systemd/system/spotify-collector.service > /dev/null <<EOF
[Unit]
Description=Spotify play history collector
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$(whoami)
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python src/collector.py
Environment=HOME=$HOME

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/spotify-collector.timer > /dev/null <<EOF
[Unit]
Description=Run Spotify collector every 15 minutes

[Timer]
OnBootSec=60
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now spotify-collector.timer

echo ""
echo "=== Setup complete ==="
echo ""
echo "Collector timer: systemctl status spotify-collector.timer"
echo "Run initial collection: .venv/bin/python src/collector.py"
echo ""
echo "To view the dashboard, sync the DB to your Mac:"
echo "  scp $(whoami)@\$(curl -s ifconfig.me):$PROJECT_DIR/data/spotify.db local-path/data/spotify.db"
