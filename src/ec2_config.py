"""EC2 connection configuration for the sync pipeline."""

from pathlib import Path

EC2_HOST = "ec2-user@44.220.160.205"
PEM_PATH = Path.home() / "Downloads" / "spotify_history.pem"
REMOTE_PROJECT = "~/spotify-history"
