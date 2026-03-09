"""Spotify authentication from environment variables."""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import spotipy
from spotipy.oauth2 import SpotifyOAuth

PROJECT_ROOT = Path(__file__).parent.parent
TOKEN_CACHE = PROJECT_ROOT / ".spotify_token_cache"

ALL_SCOPES = " ".join([
    "user-library-read",
    "user-library-modify",
    "user-top-read",
    "user-read-recently-played",
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "streaming",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-read-private",
    "user-read-email",
    "user-follow-read",
    "user-follow-modify",
])


def get_spotify_client() -> spotipy.Spotify:
    """Create an authenticated Spotify client from env vars."""
    env_file = PROJECT_ROOT / ".env"
    if load_dotenv and env_file.exists():
        load_dotenv(env_file)

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

    if not client_id or not client_secret:
        print("ERROR: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set.")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=ALL_SCOPES,
        cache_path=str(TOKEN_CACHE),
    )
    return spotipy.Spotify(auth_manager=auth_manager)


if __name__ == "__main__":
    sp = get_spotify_client()
    user = sp.current_user()
    print(f"Authenticated as: {user['display_name']} ({user['id']})")
    print(f"Account type: {user['product']}")
