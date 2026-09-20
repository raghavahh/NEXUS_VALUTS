"""
NEXUS VAULTS 2.0 - Production Scheduling & Clock Management
Enforces US Timezone Scheduling (default America/New_York), Scheduled Publication for Tomorrow,
Minimum Upload Gap Protection (MIN_UPLOAD_GAP_HOURS), and the One-Hour Preparation Guarantee.
Zero reliance on local laptop / machine time.
"""

from datetime import datetime, time, timedelta
import zoneinfo
import sqlite3
from typing import Dict, Any, Tuple, Optional
from core.config import config
from core.logging import log
from core.database import get_connection

def get_production_timezone() -> zoneinfo.ZoneInfo:
    """Returns the configured US timezone."""
    try:
        return zoneinfo.ZoneInfo(config.schedule.timezone)
    except Exception:
        log.warning(f"Invalid timezone '{config.schedule.timezone}', defaulting to America/New_York")
        return zoneinfo.ZoneInfo("America/New_York")

def get_production_clock() -> datetime:
    """Returns the current timezone-aware production datetime in the configured US timezone."""
    tz = get_production_timezone()
    return datetime.now(tz)

def get_latest_upload_time() -> Optional[datetime]:
    """Retrieves the timestamp of the most recent uploaded/scheduled video from SQLite."""
    try:
        if not config.storage.database_path.exists():
            return None
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT published_at, scheduled_publish_at
                FROM videos
                WHERE youtube_video_id IS NOT NULL
                ORDER BY id DESC LIMIT 1
            """)
            row = cur.fetchone()
        if not row:
            return None
        raw_ts = row[1] or row[0]
        if not raw_ts:
            return None

        # Clean string and parse
        ts_clean = str(raw_ts).strip()
        # If standard SQLite timestamp YYYY-MM-DD HH:MM:SS
        if " " in ts_clean and "T" not in ts_clean:
            dt = datetime.strptime(ts_clean[:19], "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        # If ISO format
        clean_iso = ts_clean.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_iso)
    except Exception as e:
        log.error(f"Could not retrieve latest upload time from database: {e}")
        return None

def get_schedule_window(target_tomorrow: bool = True) -> Dict[str, Any]:
    """
    Calculates the US-timezone production timeline for scheduled publishing:
    1. Targets TOMORROW at SCHEDULE_UPLOAD_HOUR:SCHEDULE_UPLOAD_MINUTE in America/New_York.
    2. Enforces MIN_UPLOAD_GAP_HOURS (>= 18h) after the last publication.
    3. Computes READY-BY DEADLINE (Upload Time - 1 Hour).
    4. Formats ISO-8601 UTC string for YouTube status.publishAt.
    """
    now_us = get_production_clock()
    tz = now_us.tzinfo

    upload_hour = config.schedule.upload_hour
    upload_minute = config.schedule.upload_minute
    buffer_min = config.schedule.ready_buffer_minutes
    min_gap_hours = config.schedule.min_upload_gap_hours

    # 1. Target tomorrow's date by default (ensures ~1 day between uploads)
    if target_tomorrow:
        candidate_date = (now_us + timedelta(days=1)).date()
    else:
        candidate_date = now_us.date()

    target_upload = datetime.combine(candidate_date, time(upload_hour, upload_minute), tzinfo=tz)

    # 2. Check minimum upload gap from previous upload
    latest_upload = get_latest_upload_time()
    if latest_upload:
        latest_us = latest_upload.astimezone(tz)
        min_allowed = latest_us + timedelta(hours=min_gap_hours)
        while target_upload < min_allowed:
            target_upload += timedelta(days=1)
            log.info(f"Advancing target publication date to enforce minimum {min_gap_hours}h gap: {target_upload.strftime('%Y-%m-%d %H:%M %Z')}")
    else:
        # If DB has existing uploads but parse failed, advance target +1 day conservatively
        try:
            if config.storage.database_path.exists():
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM videos WHERE youtube_video_id IS NOT NULL")
                    if cur.fetchone()[0] > 0:
                        log.warning("Database contains uploaded video(s) but latest upload time was unparseable. Advancing target slot +1 day conservatively.")
                        target_upload += timedelta(days=1)
        except Exception:
            pass

    # 3. Ensure target upload is in the future beyond the ready buffer
    while target_upload <= now_us + timedelta(minutes=buffer_min + 5):
        target_upload += timedelta(days=1)

    # 4. Ready-By Deadline is 1 hour before scheduled publication
    ready_by_deadline = target_upload - timedelta(minutes=buffer_min)
    time_to_deadline_sec = (ready_by_deadline - now_us).total_seconds()

    # 5. Format ISO-8601 UTC string for YouTube Data API v3 (status.publishAt)
    utc_dt = target_upload.astimezone(zoneinfo.ZoneInfo("UTC"))
    target_upload_iso_utc = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return {
        "current_time_us": now_us,
        "target_upload_time_us": target_upload,
        "ready_by_deadline_us": ready_by_deadline,
        "target_upload_iso_utc": target_upload_iso_utc,
        "seconds_to_deadline": time_to_deadline_sec,
        "is_ready_in_time": time_to_deadline_sec >= 0,
        "timezone_name": str(tz)
    }

def evaluate_readiness_guarantee(qc_passed: bool) -> Tuple[bool, str]:
    """
    Enforces Section 8 & Section 9:
    If video has NOT passed all required QC before the ready-by deadline:
    Mark publication_status=DEFERRED.
    Never rush or bypass QC to meet a clock.
    """
    sched = get_schedule_window()
    now_str = sched["current_time_us"].strftime("%Y-%m-%d %H:%M:%S %Z")
    ready_by_str = sched["ready_by_deadline_us"].strftime("%Y-%m-%d %H:%M:%S %Z")
    upload_str = sched["target_upload_time_us"].strftime("%Y-%m-%d %H:%M:%S %Z")

    log.info(f"[PRODUCTION CLOCK] US Time: {now_str}")
    log.info(f"[PRODUCTION TIMELINE] Ready-By: {ready_by_str} | Scheduled Publish: {upload_str}")

    if not qc_passed:
        log.error("Mandatory QC verification failed. Scheduled publication strictly blocked.")
        return False, "DEFERRED_QC_FAILURE"

    if sched["is_ready_in_time"] or config.app.mode != "production":
        log.info(f"1-Hour Readiness Guarantee satisfied. Video ready for scheduled upload at {upload_str}.")
        return True, "READY"
    else:
        log.warning(
            f"Video completed after Ready-By deadline ({ready_by_str}). "
            "Enforcing Section 9: publication_status=DEFERRED to protect quality integrity."
        )
        return False, "DEFERRED_PAST_DEADLINE"
