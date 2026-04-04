# timelapse_capture.py  — resilient scheduler
import ctypes
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_EXECUTED
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from tzlocal import get_localzone

# --- CONFIG ---
STREAM_URL = "https://558312d54930d.streamlock.net/live/ccrb2.fois.axis.stream/playlist.m3u8"
_env_ff = (os.environ.get("PARKING_LOT_FFMPEG") or "").strip()
FFMPEG = _env_ff or "ffmpeg"  # or set PARKING_LOT_FFMPEG to a full path


def _default_base_dir() -> Path:
    """Prefer PARKING_LOT_IMAGES_DIR, then OneDrive sync roots (set by Windows), else Pictures."""
    override = (os.environ.get("PARKING_LOT_IMAGES_DIR") or "").strip()
    if override:
        return Path(override)
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        root = (os.environ.get(key) or "").strip()
        if root:
            return Path(root) / "ParkingLotImages"
    return Path.home() / "Pictures" / "ParkingLotImages"


BASE_DIR = _default_base_dir()
USE_DATE_SUBFOLDERS = True
RETENTION_DAYS = 30
# Off by default so a wrong BASE_DIR cannot delete unrelated folders named yyyy-MM-dd.
_ENABLE_PRUNE_RAW = (os.environ.get("PARKING_LOT_ENABLE_RETENTION_PRUNE") or "").strip().lower()
ENABLE_RETENTION_PRUNE = _ENABLE_PRUNE_RAW in ("1", "true", "yes", "on")
ZIP_YESTERDAY = False
JPEG_QUALITY = "2"  # lower=better quality (1–31)
FFMPEG_COMMON = ["-hide_banner", "-loglevel", "error", "-y", "-rw_timeout", "15000000"]
FFMPEG_TIMEOUT_SEC = 60  # kill ffmpeg if it doesn't finish quickly
LOG_PATH = BASE_DIR / "timelapse.log"
STATUS_PATH = BASE_DIR / "status.json"
# ---------------

# ---------- Logging ----------
BASE_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8")
    ],
)


def write_status(**kw):
    base = {"updated_at": datetime.now().isoformat(timespec="seconds")}
    base.update(kw)
    try:
        STATUS_PATH.write_text(json.dumps(base, indent=2))
    except Exception as e:
        logging.warning("status.json write failed: %s", e)


# ---------- Anti-sleep (Windows) ----------
def prevent_sleep():
    if platform.system() != "Windows":
        return
    # Prevent the system from sleeping while this process is running.
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_AWAYMODE_REQUIRED = 0x00000040  # keep system awake without waking display
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        )
    except Exception as e:
        logging.warning("prevent_sleep failed: %s", e)


# ---------- Paths & housekeeping ----------
def get_out_dir(dt: datetime) -> Path:
    return (BASE_DIR / dt.strftime("%Y-%m-%d")) if USE_DATE_SUBFOLDERS else BASE_DIR


def prune_old():
    if not ENABLE_RETENTION_PRUNE or RETENTION_DAYS <= 0:
        return
    # Match tray app: calendar-day threshold (strict yyyy-MM-dd names only, via strptime).
    today = datetime.now().date()
    oldest_keep = today - timedelta(days=RETENTION_DAYS)
    try:
        for child in BASE_DIR.iterdir():
            try:
                if USE_DATE_SUBFOLDERS and child.is_dir():
                    day = datetime.strptime(child.name, "%Y-%m-%d").date()
                    if day >= oldest_keep:
                        continue
                    if (BASE_DIR / f"{child.name}.zip").exists():
                        continue
                    shutil.rmtree(child)
                    logging.info("Pruned folder %s (before keep threshold %s)", child.name, oldest_keep)
                elif not USE_DATE_SUBFOLDERS and child.is_file() and child.suffix.lower() == ".jpg":
                    if datetime.fromtimestamp(child.stat().st_mtime).date() < oldest_keep:
                        child.unlink(missing_ok=True)
            except ValueError:
                continue
    except Exception as e:
        logging.warning("Prune error: %s", e)


def zip_yesterday():
    if not ZIP_YESTERDAY or not USE_DATE_SUBFOLDERS:
        return
    y = datetime.now() - timedelta(days=1)
    folder = get_out_dir(y)
    zip_path = BASE_DIR / f"{folder.name}.zip"
    if folder.exists() and not zip_path.exists():
        try:
            shutil.make_archive(str(zip_path.with_suffix('')), 'zip', root_dir=folder)
            shutil.rmtree(folder)
            logging.info("Zipped %s -> %s", folder.name, zip_path.name)
        except Exception as e:
            logging.warning("Zip error: %s", e)


def housekeeping():
    zip_yesterday()
    prune_old()


# ---------- Capture ----------
def capture_one():
    dt = datetime.now()
    out_dir = get_out_dir(dt)
    out_dir.mkdir(parents=True, exist_ok=True)

    final_name = f"pl-{dt.strftime('%Y-%m-%d-%H-%M-%S')}.jpg"
    final_path = out_dir / final_name
    tmp_path = out_dir / (final_name + ".part")  # keep .part; we set format explicitly

    cmd = [
        FFMPEG, *FFMPEG_COMMON,
        "-i", STREAM_URL,
        "-f", "image2",
        "-vcodec", "mjpeg",
        "-q:v", JPEG_QUALITY,
        "-vframes", "1",
        str(tmp_path)
    ]

    # Try up to 3 times; kill/timeout ffmpeg if it stalls
    for attempt in range(1, 4):
        try:
            prevent_sleep()  # reassert before heavy work
            subprocess.run(cmd, check=True, timeout=FFMPEG_TIMEOUT_SEC)
            tmp_path.replace(final_path)  # atomic finalize
            # Make dashboard artifacts
            try:
                shutil.copy2(final_path, BASE_DIR / "latest.jpg")
            except Exception:
                pass
            disk = shutil.disk_usage(BASE_DIR)
            write_status(
                ok=True,
                last_capture=str(final_path),
                last_capture_time=datetime.now().isoformat(timespec="seconds"),
                free_gb=round(disk.free / 1e9, 2),
            )
            logging.info("Saved -> %s", final_path)
            return
        except subprocess.TimeoutExpired:
            logging.warning("ffmpeg timeout after %ss (attempt %d/3)", FFMPEG_TIMEOUT_SEC, attempt)
        except subprocess.CalledProcessError as e:
            logging.warning("ffmpeg failed (attempt %d/3, exit %s)", attempt, e.returncode)
        except Exception as e:
            logging.warning("Unexpected capture error (attempt %d/3): %s", attempt, e)
        time.sleep(3)

    write_status(ok=False, error="ffmpeg failed after retries")
    logging.error("Capture failed after retries")


# ---------- Observability ----------
def heartbeat():
    # Proves the scheduler thread is alive between runs.
    logging.info("heartbeat: scheduler alive")
    prevent_sleep()  # reassert every 5 minutes


def on_sched_event(event):
    if event.code == EVENT_JOB_MISSED:
        logging.warning("MISSED job %s scheduled for %s", event.job_id, event.scheduled_run_time)
    elif event.code == EVENT_JOB_ERROR:
        logging.error("ERROR in job %s", getattr(event, "job_id", "?"))
    elif event.code == EVENT_JOB_EXECUTED:
        # Uncomment if you want every execution logged here (capture already logs)
        # logging.info("executed job %s", event.job_id)
        pass


# ---------- Main ----------
if __name__ == "__main__":
    tz = get_localzone()

    job_defaults = {
        "coalesce": True,  # collapse backlog into one run after wake
        "misfire_grace_time": 7200,  # 2h grace so a short sleep doesn't lose runs
        "max_instances": 1
    }
    sched = BlockingScheduler(timezone=tz, job_defaults=job_defaults)
    sched.add_listener(on_sched_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_EXECUTED)

    # Immediate test capture on startup
    capture_one()

    # Capture schedules
    sched.add_job(capture_one, CronTrigger(hour="18-23", minute="0"), id="cap_evening")
    sched.add_job(capture_one, CronTrigger(hour="0-6", minute="0"), id="cap_overnight")
    sched.add_job(capture_one, CronTrigger(hour="7-8", minute="0,10,20,30,40,50"), id="cap_morning_rush")
    sched.add_job(capture_one, CronTrigger(hour="9-15", minute="0"), id="cap_daytime")
    sched.add_job(capture_one, CronTrigger(hour="16-17", minute="0,10,20,30,40,50"), id="cap_evening_rush")

    # Daily housekeeping
    sched.add_job(housekeeping, CronTrigger(hour="3", minute="10"), id="housekeeping")

    # Heartbeat & anti-sleep reassert (every 5 minutes)
    sched.add_job(heartbeat, IntervalTrigger(minutes=5), id="heartbeat")

    logging.info("Scheduler started | TZ=%s | logs: %s", tz, LOG_PATH)
    prevent_sleep()
    sched.start()
