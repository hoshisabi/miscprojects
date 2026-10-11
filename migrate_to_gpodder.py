#!/usr/bin/env python3
"""
Migrate PodcastAddict backup to gpodder.net

Uploads:
  - Subscriptions (all subscribed feeds)
  - Listened episodes (marked as fully played)
  - In-progress episodes (with playback position)

Usage:
    python migrate_to_gpodder.py <backup_file> --username USER --password PASS [--device DEVICE]

The device name identifies this sync client in gpodder.net (default: "migration").
Any gpodder-compatible app (AntennaPod, gPodder) can then pull from the same account.
"""

import sys
import json
import sqlite3
import zipfile
import tempfile
import datetime
import argparse
import urllib.request
import urllib.parse
import http.cookiejar
from pathlib import Path

GPODDER_BASE = "https://gpodder.net"
BATCH_SIZE = 30  # conservative batch size for episode actions


# --- HTTP helpers ---

import base64

def make_opener(username, password):
    cookie_jar = http.cookiejar.CookieJar()
    cookie_handler = urllib.request.HTTPCookieProcessor(cookie_jar)
    opener = urllib.request.build_opener(cookie_handler)
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    opener.addheaders = [("Authorization", f"Basic {credentials}")]
    return opener


def api_post(opener, path, data):
    url = GPODDER_BASE + path
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                  headers={"Content-Type": "application/json"})
    with opener.open(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def api_put(opener, path, data):
    url = GPODDER_BASE + path
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PUT",
                                  headers={"Content-Type": "application/json"})
    with opener.open(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def login(opener, username, password):
    url = GPODDER_BASE + f"/api/2/auth/{username}/login.json"
    req = urllib.request.Request(url, data=b"", method="POST")
    with opener.open(req) as resp:
        return resp.status == 200


# --- Database helpers ---

def extract_db(backup_path: Path, tmp_dir: Path) -> Path:
    if not zipfile.is_zipfile(backup_path):
        sys.exit(f"Not a valid PodcastAddict backup (expected zip): {backup_path}")
    with zipfile.ZipFile(backup_path) as z:
        db_names = [n for n in z.namelist() if n.endswith(".db")]
        if not db_names:
            sys.exit("No .db file found inside backup")
        db_path = tmp_dir / db_names[0]
        with z.open(db_names[0]) as src, open(db_path, "wb") as dst:
            dst.write(src.read())
    return db_path


def ms_to_s(ms):
    return int(ms // 1000) if ms and ms > 0 else 0


def ms_to_ts(ms):
    if ms and ms > 0:
        return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# --- Migration steps ---

def upload_subscriptions(opener, cur, username, device):
    cur.execute("""
        SELECT feed_url FROM podcasts
        WHERE subscribed_status = 1 AND is_virtual = 0 AND feed_url IS NOT NULL
        ORDER BY name COLLATE NOCASE
    """)
    feed_urls = [row[0] for row in cur.fetchall()]
    print(f"\nUploading {len(feed_urls)} subscriptions to device '{device}'...")
    result = api_post(opener, f"/api/2/subscriptions/{username}/{device}.json",
                      {"add": feed_urls, "remove": []})
    skipped = result.get("update_urls", [])
    if skipped:
        print(f"  Note: {len(skipped)} URLs were redirected/updated by gpodder.net")
    print(f"  Done.")


def build_episode_actions(cur):
    actions = []

    # Fully listened
    cur.execute("""
        SELECT p.feed_url, e.download_url, e.playbackDate, e.duration_ms
        FROM episodes e
        JOIN podcasts p ON e.podcast_id = p._id
        WHERE e.seen_status = 1
          AND e.download_url IS NOT NULL AND e.download_url != ''
          AND p.feed_url IS NOT NULL
    """)
    for feed_url, ep_url, pb_date, dur_ms in cur.fetchall():
        total = ms_to_s(dur_ms)
        actions.append({
            "podcast": feed_url,
            "episode": ep_url,
            "action": "play",
            "timestamp": ms_to_ts(pb_date),
            "started": 0,
            "position": total,
            "total": total,
        })

    # In-progress
    cur.execute("""
        SELECT p.feed_url, e.download_url, e.playbackDate,
               e.position_to_resume, e.duration_ms
        FROM episodes e
        JOIN podcasts p ON e.podcast_id = p._id
        WHERE e.seen_status = 0
          AND e.position_to_resume > 0
          AND e.download_url IS NOT NULL AND e.download_url != ''
          AND p.feed_url IS NOT NULL
    """)
    for feed_url, ep_url, pb_date, pos_ms, dur_ms in cur.fetchall():
        actions.append({
            "podcast": feed_url,
            "episode": ep_url,
            "action": "play",
            "timestamp": ms_to_ts(pb_date),
            "started": 0,
            "position": ms_to_s(pos_ms),
            "total": ms_to_s(dur_ms),
        })

    return actions


def upload_episode_actions(opener, cur, username):
    actions = build_episode_actions(cur)
    total = len(actions)
    print(f"\nUploading {total} episode actions in batches of {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = actions[i:i + BATCH_SIZE]
        result = api_post(opener, f"/api/2/episodes/{username}.json", batch)
        updated = result.get("update_urls", [])
        n = min(i + BATCH_SIZE, total)
        print(f"  {n}/{total}", end="\r")

    print(f"\n  Done.")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Migrate PodcastAddict backup to gpodder.net")
    parser.add_argument("backup", help="Path to PodcastAddict .backup file")
    parser.add_argument("--username", required=True, help="gpodder.net username")
    parser.add_argument("--password", required=True, help="gpodder.net password")
    parser.add_argument("--device", default="migration", help="Device name on gpodder.net (default: migration)")
    parser.add_argument("--subscriptions-only", action="store_true", help="Only upload subscriptions, skip episode history")
    args = parser.parse_args()

    backup_path = Path(args.backup).expanduser().resolve()
    if not backup_path.exists():
        sys.exit(f"File not found: {backup_path}")

    opener = make_opener(args.username, args.password)

    print(f"Logging in to gpodder.net as '{args.username}'...")
    if not login(opener, args.username, args.password):
        sys.exit("Login failed — check username and password")
    print("  Logged in.")

    with tempfile.TemporaryDirectory() as tmp:
        db_path = extract_db(backup_path, Path(tmp))
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        upload_subscriptions(opener, cur, args.username, args.device)

        if not args.subscriptions_only:
            upload_episode_actions(opener, cur, args.username)

        conn.close()  # must close before tempdir cleanup on Windows

    print("\nMigration complete.")
    print(f"Point AntennaPod or gPodder at gpodder.net with username '{args.username}' to sync.")


if __name__ == "__main__":
    main()
