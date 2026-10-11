#!/usr/bin/env python3
"""
Export PodcastAddict listening history from a .backup file.

Usage:
    python podcastaddict_export.py <backup_file> [output_dir]

Output (in output_dir, defaulting to backup file's directory):
    subscriptions.csv   - all subscribed podcasts with folder/tag assignments
    listened.csv        - all fully-listened episodes
    in_progress.csv     - episodes with partial playback position
    queue.csv           - ordered playback queue
    chapters.csv        - chapter markers for episodes that have them
"""

import sys
import csv
import sqlite3
import zipfile
import datetime
import tempfile
from pathlib import Path


def ts(ms):
    if ms and ms > 0:
        return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")
    return ""


def duration_str(ms):
    if ms and ms > 0:
        mins = ms // 60000
        return f"{mins}m"
    return ""


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


def export(backup_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = extract_db(backup_path, Path(tmp))
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # --- Subscriptions (with tags/folders) ---
        subs_path = output_dir / "subscriptions.csv"
        cur.execute("""
            SELECT p.name, p.author, p.feed_url, p.automaticRefresh,
                   p.last_played_episode_date,
                   GROUP_CONCAT(t.name, '; ') AS tags
            FROM podcasts p
            LEFT JOIN tag_relation tr ON tr.podcast_id = p._id
            LEFT JOIN tags t ON t._id = tr.tag_id
            WHERE p.subscribed_status = 1 AND p.is_virtual = 0
            GROUP BY p._id
            ORDER BY p.name COLLATE NOCASE
        """)
        with open(subs_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["podcast", "author", "feed_url", "auto_refresh", "last_played", "tags"])
            for name, author, feed_url, auto_refresh, last_played, tags in cur.fetchall():
                w.writerow([name, author or "", feed_url or "",
                             bool(auto_refresh), ts(last_played), tags or ""])
        print(f"Subscriptions -> {subs_path}")

        # --- Listened episodes ---
        listened_path = output_dir / "listened.csv"
        cur.execute("""
            SELECT p.name, e.name, e.publication_date, e.playbackDate,
                   e.duration_ms, e.download_url
            FROM episodes e
            JOIN podcasts p ON e.podcast_id = p._id
            WHERE e.seen_status = 1
            ORDER BY p.name COLLATE NOCASE, e.publication_date
        """)
        with open(listened_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["podcast", "episode", "published", "listened_at", "duration", "url"])
            for podcast, episode, pub, pb, dur, url in cur.fetchall():
                w.writerow([podcast, episode, ts(pub), ts(pb), duration_str(dur), url or ""])
        print(f"Listened       -> {listened_path}")

        # --- In-progress episodes ---
        inprog_path = output_dir / "in_progress.csv"
        cur.execute("""
            SELECT p.name, e.name, e.publication_date, e.position_to_resume,
                   e.duration_ms, e.download_url
            FROM episodes e
            JOIN podcasts p ON e.podcast_id = p._id
            WHERE e.seen_status = 0
              AND e.position_to_resume IS NOT NULL
              AND e.position_to_resume > 0
            ORDER BY p.name COLLATE NOCASE, e.publication_date
        """)
        with open(inprog_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["podcast", "episode", "published", "position", "duration", "url"])
            for podcast, episode, pub, pos, dur, url in cur.fetchall():
                pos_str = duration_str(pos)
                w.writerow([podcast, episode, ts(pub), pos_str, duration_str(dur), url or ""])
        print(f"In progress    -> {inprog_path}")

        # --- Queue ---
        queue_path = output_dir / "queue.csv"
        cur.execute("""
            SELECT ol.rank, p.name, e.name, e.publication_date,
                   e.position_to_resume, e.duration_ms, e.download_url
            FROM ordered_list ol
            JOIN episodes e ON ol.id = e._id
            JOIN podcasts p ON e.podcast_id = p._id
            WHERE ol.type = 1
            ORDER BY ol.rank
        """)
        with open(queue_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["rank", "podcast", "episode", "published", "position", "duration", "url"])
            for rank, podcast, episode, pub, pos, dur, url in cur.fetchall():
                w.writerow([rank, podcast, episode, ts(pub),
                             duration_str(pos), duration_str(dur), url or ""])
        print(f"Queue          -> {queue_path}")

        # --- Chapters ---
        chapters_path = output_dir / "chapters.csv"
        cur.execute("""
            SELECT p.name, e.name, e.publication_date, c.start, c.name, c.url
            FROM chapters c
            JOIN podcasts p ON c.podcastId = p._id
            JOIN episodes e ON c.episodeId = e._id
            ORDER BY p.name COLLATE NOCASE, e.publication_date, c.start
        """)
        with open(chapters_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["podcast", "episode", "published", "chapter_start_ms", "chapter_title", "chapter_url"])
            for podcast, episode, pub, start, title, url in cur.fetchall():
                w.writerow([podcast, episode, ts(pub), start, title or "", url or ""])
        print(f"Chapters       -> {chapters_path}")

        conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    backup_path = Path(sys.argv[1]).expanduser().resolve()
    if not backup_path.exists():
        sys.exit(f"File not found: {backup_path}")

    output_dir = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else backup_path.parent
    export(backup_path, output_dir)


if __name__ == "__main__":
    main()
