"""
NEXUS VAULTS 2.0 - Live Channel Analytics & Demand Feedback Synchronizer
OWN CHANNEL: YouTube Analytics API v2 (authenticated OAuth) — authoritative.
COMPETITORS: public YouTube Data API / yt-dlp — separate module (research/yt_intel.py).

yt-dlp is NOT used as an own-channel fallback. If the authenticated Analytics API is
unavailable, the run logs a warning and proceeds without analytics — it does not silently
substitute public metadata for private performance data.
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from core.database import get_connection
from core.config import config
from core.logging import log
from analytics.decision_engine import process_feedback_loop


def _refresh_oauth_token() -> Optional[str]:
    """
    Exchanges the configured OAuth2 Refresh Token for a fresh Access Token.
    Returns the access token string or None if refresh fails.
    """
    client_id = config.youtube.client_id
    client_secret = config.youtube.client_secret
    refresh_token = config.youtube.refresh_token
    if not (client_id and client_secret and refresh_token):
        return None

    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=payload,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
            return token_data.get("access_token") or None
    except Exception as e:
        log.debug(f"OAuth token refresh notice: {e}")
        return None


def _fetch_youtube_data_api_stats(video_ids: List[str], access_token: str) -> Dict[str, Dict[str, Any]]:
    """
    Queries YouTube Data API v3 videos?part=statistics,status for privacy state
    and basic counts. Used as a supplement to Analytics API (not as a standalone fallback).
    """
    if not video_ids or not access_token:
        return {}
    stats_url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=statistics,status&id={','.join(video_ids)}"
    )
    try:
        req = urllib.request.Request(stats_url, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = {}
            for item in data.get("items", []):
                vid = item.get("id")
                st = item.get("statistics", {})
                stat = item.get("status", {})
                results[vid] = {
                    "views": int(st.get("viewCount", 0)),
                    "likes": int(st.get("likeCount", 0)),
                    "comments": int(st.get("commentCount", 0)),
                    "privacy_status": stat.get("privacyStatus", "private"),
                    "publish_at": stat.get("publishAt"),
                }
            return results
    except Exception as e:
        log.debug(f"YouTube Data API stats query notice: {e}")
        return {}


def _fetch_youtube_analytics_api(video_ids: List[str], access_token: str) -> Dict[str, Dict[str, Any]]:
    """
    Authoritative own-channel retention & engagement analytics.
    Queries YouTube Analytics API v2 (youtubeanalytics.googleapis.com/v2/reports)
    for private per-video metrics: retention, watch duration, engagement, subs gained.

    Metrics returned:
      - views, estimatedMinutesWatched, averageViewDuration, averageViewPercentage
      - subscribersGained, likes, comments

    NOTE: YouTube Shorts 'swipe-through rate' (viewed vs swiped) is not a public Analytics
    API v2 dimension. averageViewPercentage is used as the primary retention proxy.
    If the Shorts-specific audience retention endpoint becomes available, plug it in here.
    """
    if not video_ids or not access_token:
        return {}

    # Use the last 3 years as the observation window; Analytics API requires a date range
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=config.analytics.observation_window_days)).strftime("%Y-%m-%d")
    filters = "video==" + ",".join(video_ids)
    metrics = (
        "views,estimatedMinutesWatched,averageViewDuration,"
        "averageViewPercentage,subscribersGained,likes,comments"
    )
    url = (
        f"https://youtubeanalytics.googleapis.com/v2/reports"
        f"?ids=channel==MINE"
        f"&startDate={start_date}"
        f"&endDate={end_date}"
        f"&metrics={metrics}"
        f"&dimensions=video"
        f"&filters={urllib.parse.quote(filters)}"
    )

    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        col_headers = [h["name"] for h in data.get("columnHeaders", [])]
        results: Dict[str, Dict[str, Any]] = {}
        for row in data.get("rows", []):
            row_dict = dict(zip(col_headers, row))
            vid = row_dict.get("video")
            if not vid:
                continue
            # averageViewPercentage is the closest public proxy for Shorts retention
            avg_pct = float(row_dict.get("averageViewPercentage", 0.0))
            avg_dur = float(row_dict.get("averageViewDuration", 0.0))
            # NOTE: YouTube Shorts 'swipe-through rate' (viewed vs. swiped) is NOT available
            # in the public YouTube Analytics API v2. averageViewPercentage is the only available
            # retention proxy. It is used directly as the hook_signal input in metrics.py.
            # When/if YouTube exposes a Shorts-specific swipe metric, add it here.
            results[vid] = {
                "views": int(row_dict.get("views", 0)),
                "likes": int(row_dict.get("likes", 0)),
                "comments": int(row_dict.get("comments", 0)),
                "avg_view_duration_sec": avg_dur,
                "avg_percentage_viewed": avg_pct,
                # Hook hold rate proxy: same as avg_percentage_viewed (only available signal)
                # Named separately to clarify its semantic role in the scoring formula
                "hook_hold_rate_pct": avg_pct,
                "subscribers_gained": int(row_dict.get("subscribersGained", 0)),
                "source": "YouTube Analytics API v2 (Authenticated)"
            }
        return results
    except Exception as e:
        log.debug(f"YouTube Analytics API v2 query notice: {e}")
        return {}


def _parse_db_timestamp(raw: Optional[str]) -> Optional[datetime]:
    """Parses SQLite/ISO timestamps into timezone-aware UTC datetimes."""
    if not raw:
        return None
    ts = str(raw).strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f+00:00", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(ts[:26] if "." in ts else ts[:19], fmt if "%f" in fmt or " " in fmt else fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _is_observable_now(row) -> bool:
    """
    A video only generates real performance data once it is actually PUBLIC.
    Scheduled (publishAt in the future) videos return zero-view analytics that
    would poison the learning loop — they must be excluded from syncing.
    """
    now = datetime.now(timezone.utc)
    scheduled = _parse_db_timestamp(row["scheduled_publish_at"]) if "scheduled_publish_at" in row.keys() else None
    if scheduled is not None:
        return scheduled <= now
    published = _parse_db_timestamp(row["published_at"]) if "published_at" in row.keys() else None
    if published is not None:
        return published <= now
    # No timestamp at all — treat as observable only if it is not freshly scheduled
    return (row["upload_status"] or "") != "SCHEDULED"


def sync_channel_analytics() -> Dict[str, Any]:
    """
    Syncs live YouTube metrics for own published videos via authenticated APIs only.
    1. Fetches PUBLISHED videos (publishAt already passed) from the database —
       scheduled/future videos are excluded to avoid zero-view pollution.
    2. Refreshes OAuth2 access token.
    3. Queries YouTube Analytics API v2 for retention/engagement (authoritative).
    4. Supplements with YouTube Data API v3 for basic counts if needed.
    5. Does NOT fall back to yt-dlp for own-channel analytics.
    6. Triggers process_feedback_loop() to recalculate algorithm demand weights.

    If the Analytics API is unavailable (e.g. no OAuth credentials), the run
    proceeds without analytics — it does NOT silently substitute public metadata.
    """
    videos_to_check = []
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, file_number, youtube_video_id, title, upload_status,
                   scheduled_publish_at, published_at
            FROM videos
            WHERE youtube_video_id IS NOT NULL AND upload_status NOT IN ('DEFERRED', 'DEFERRED_UPLOAD_FAILED')
            ORDER BY id DESC LIMIT 15
        """)
        all_rows = cur.fetchall()

    videos_to_check = [r for r in all_rows if _is_observable_now(r)]
    skipped = len(all_rows) - len(videos_to_check)
    if skipped:
        log.info(f"[ANALYTICS] Excluding {skipped} scheduled/unpublished video(s) — zero-view data would poison the learning loop.")

    if not videos_to_check:
        log.info("No published (observable) videos found in database to sync analytics for.")
        return {"synced_count": 0, "status": "NO_VIDEOS"}

    # Refresh OAuth token once for this sync run
    access_token = _refresh_oauth_token()
    if not access_token:
        log.warning(
            "[ANALYTICS] OAuth token refresh failed. Own-channel analytics sync skipped. "
            "yt-dlp is NOT used as a fallback for own-channel analytics. "
            "Ensure YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN are set."
        )
        return {"synced_count": 0, "status": "NO_CREDENTIALS"}

    video_ids = [v["youtube_video_id"] for v in videos_to_check]
    log.info(f"Syncing authoritative channel analytics for {len(video_ids)} published Shorts via YouTube Analytics API...")

    # Authoritative: YouTube Analytics API v2 (retention, watch time, engagement)
    analytics_stats = _fetch_youtube_analytics_api(video_ids, access_token)
    # Supplement: YouTube Data API v3 (basic counts + privacy state)
    data_api_stats = _fetch_youtube_data_api_stats(video_ids, access_token)

    synced_items = []
    for v in videos_to_check:
        v_id = v["youtube_video_id"]
        file_num = v["file_number"]
        video_db_id = v["id"]

        # Prefer Analytics API data; supplement counts from Data API if Analytics missing them
        a_stat = analytics_stats.get(v_id)
        d_stat = data_api_stats.get(v_id)

        if not a_stat and not d_stat:
            log.debug(f"FILE #{file_num:03d}: No analytics data returned from either API for {v_id}.")
            continue

        if a_stat:
            views = a_stat["views"] or (d_stat["views"] if d_stat else 0)
            likes = a_stat["likes"] or (d_stat["likes"] if d_stat else 0)
            comments = a_stat["comments"] or (d_stat["comments"] if d_stat else 0)
            avg_view_pct = a_stat["avg_percentage_viewed"]
            avg_view_dur = a_stat["avg_view_duration_sec"]
            # hook_hold_rate_pct == avg_percentage_viewed (single source — no separate swipe data in API)
            viewed_vs_swiped = a_stat["hook_hold_rate_pct"]
            subs_gained = a_stat["subscribers_gained"]
            source_label = a_stat["source"]
        else:
            # Data API only (no retention metrics available — record what we have)
            views = d_stat["views"]
            likes = d_stat["likes"]
            comments = d_stat["comments"]
            avg_view_pct = 0.0
            avg_view_dur = 0.0
            viewed_vs_swiped = 0.0
            subs_gained = 0
            source_label = "YouTube Data API v3 (basic counts only — no retention data)"
            log.warning(f"FILE #{file_num:03d}: Analytics API unavailable; recording basic counts only. "
                        "Retention metrics will be missing from this sync.")

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO analytics (
                    video_id, youtube_video_id, views, likes, comments,
                    shown_in_feed, viewed_vs_swiped_pct, avg_percentage_viewed,
                    avg_view_duration_sec, subscribers_gained, recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                video_db_id, v_id, views, likes, comments,
                0,  # impressions/shown_in_feed is NOT available via Analytics API v2 — never fabricated
                viewed_vs_swiped,
                avg_view_pct,
                avg_view_dur,
                subs_gained
            ))
            conn.commit()

        synced_items.append({
            "file_number": file_num,
            "video_id": v_id,
            "views": views,
            "likes": likes,
            "comments": comments,
            "avg_view_pct": avg_view_pct,
            "source": source_label
        })
        log.info(
            f"FILE #{file_num:03d} analytics synced via {source_label}: "
            f"{views} views, {likes} likes, {avg_view_pct:.1f}% avg retention."
        )

    # Trigger Self-Learning Decision Engine (only if we have fresh data)
    if synced_items:
        process_feedback_loop()
        log.info("Self-learning feedback loop completed. Future research topics and script hooks updated to match channel demand.")

    return {
        "synced_count": len(synced_items),
        "items": synced_items,
        "status": "SUCCESS" if synced_items else "NO_DATA"
    }
