# Spotify History -- Cheat Sheet

All commands are copy-paste ready.

**Project directory:**
```bash
cd "/Users/adriansoto/Documents/C - Projects/spotify-library"
```

---

## Dashboard

```bash
# Start
.venv/bin/streamlit run src/dashboard.py

# Open in browser (if it doesn't auto-open)
open http://localhost:8501

# Stop: Ctrl+C in the terminal where it's running
```

Once running, click **Refresh from EC2** in the dashboard to pull the latest data.

---

## Sync Database from EC2 (without dashboard)

```bash
# One-liner: collect fresh data on EC2, then copy DB to Mac
ssh -i ~/Downloads/spotify_history.pem ec2-user@44.220.160.205 \
  "cd ~/spotify-history && .venv/bin/python src/collector.py" && \
scp -i ~/Downloads/spotify_history.pem \
  ec2-user@44.220.160.205:~/spotify-history/data/spotify.db data/spotify.db

# Or use the sync script (syncs DB + offers to launch dashboard)
bash sync-db.sh ec2-user@44.220.160.205
```

---

## Stats CLI

Run from the project directory.

```bash
# Overall summary
.venv/bin/python src/stats.py summary

# Top tracks / artists / albums
.venv/bin/python src/stats.py top-tracks --limit 20
.venv/bin/python src/stats.py top-tracks --days 7 --limit 10
.venv/bin/python src/stats.py top-artists --limit 10
.venv/bin/python src/stats.py top-albums --days 30

# Recent play history
.venv/bin/python src/stats.py history --days 7 --limit 50

# Skipped tracks
.venv/bin/python src/stats.py skipped --days 7

# Look up a specific track or artist
.venv/bin/python src/stats.py track "Peg"
.venv/bin/python src/stats.py artist "Steely Dan"
```

Common flags: `--days N` (filter to last N days), `--limit N` (number of results).

---

## EC2 Instance

```bash
# SSH into the instance
ssh -i ~/Downloads/spotify_history.pem ec2-user@44.220.160.205

# Check collector timer status
ssh -i ~/Downloads/spotify_history.pem ec2-user@44.220.160.205 \
  "systemctl status spotify-collector.timer"

# View last collector run log
ssh -i ~/Downloads/spotify_history.pem ec2-user@44.220.160.205 \
  "journalctl -u spotify-collector.service --no-pager -n 20"

# Manually run the collector now
ssh -i ~/Downloads/spotify_history.pem ec2-user@44.220.160.205 \
  "cd ~/spotify-history && .venv/bin/python src/collector.py"
```

---

## AWS (start / stop / check instance)

Instance ID: `i-05f398a7da4ae17ed`

```bash
# Check instance state
aws ec2 describe-instance-status --instance-ids i-05f398a7da4ae17ed \
  --query 'InstanceStatuses[0].InstanceState.Name' --output text

# Stop instance (saves money when not collecting)
aws ec2 stop-instances --instance-ids i-05f398a7da4ae17ed

# Start instance
aws ec2 start-instances --instance-ids i-05f398a7da4ae17ed

# Get current public IP (changes after stop/start)
aws ec2 describe-instances --instance-ids i-05f398a7da4ae17ed \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

Note: the public IP changes every time you stop/start the instance. Update `src/ec2_config.py` with the new IP if it changes.
