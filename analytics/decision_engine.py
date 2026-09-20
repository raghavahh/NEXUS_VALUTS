"""
NEXUS VAULTS 2.0 - Self-Learning Decision Engine
Updates topic cluster and hook weights in SQLite based on algorithm feedback.

DESIGN RULES:
1. Weight updates only execute when sample_count >= ANALYTICS_MIN_SAMPLE_COUNT.
   Bootstrap weights hold until enough real data exists to justify changes.
2. Every weight change is logged with its delta, sample count, and score basis
   so the change is fully explainable and auditable.
3. The observation window (ANALYTICS_OBSERVATION_WINDOW_DAYS) limits which data
   is used — stale data from months ago should not influence tomorrow's decisions.
4. The feedback loop updates weights for the NEXT run, not the current run.
   It reads analytics from PREVIOUSLY published videos only.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from core.database import get_connection, update_weight
from core.config import config
from core.logging import log
from analytics.metrics import compute_shorts_performance_score

# A video needs this many views before its ratios are statistically meaningful.
# Below it, a single like can saturate the engagement signal (1 like / 3 views = 33%
# likes-per-view) and produce wildly inflated scores. Algorithmic guard, not config.
MIN_VIEWS_FOR_LEARNING = 50


def process_feedback_loop():
    """
    Reads recent video analytics within the configured observation window,
    computes performance scores, and updates dynamic feedback weights.

    Guards:
    - Only processes rows within ANALYTICS_OBSERVATION_WINDOW_DAYS.
    - Only ONE observation per video (latest snapshot) — repeated syncs must not
      double-count a single video's performance.
    - Only videos with >= MIN_VIEWS_FOR_LEARNING views contribute.
    - Only commits weight updates when per-key sample_count >= ANALYTICS_MIN_SAMPLE_COUNT.
    - Logs every adjustment with its delta, score, and justification.
    """
    log.info("Running Decision Engine feedback loop...")

    min_samples = config.analytics.min_sample_count
    window_days = config.analytics.observation_window_days
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT a.video_id, v.hook_type, t.cluster, a.viewed_vs_swiped_pct, a.avg_percentage_viewed,
               a.views, a.likes, a.subscribers_gained, a.recorded_at,
               v.title as video_title
        FROM analytics a
        JOIN videos v ON a.video_id = v.id
        JOIN topics t ON v.topic_id = t.id
        WHERE a.recorded_at >= ?
        ORDER BY a.recorded_at DESC
        LIMIT 60
        """, (cutoff_date,))
        raw_rows = cursor.fetchall()

        if not raw_rows:
            log.info(f"No analytics data within observation window ({window_days} days). No weight updates applied.")
            return

        # Deduplicate: latest snapshot per video only (rows are DESC by recorded_at)
        seen_video_ids = set()
        rows = []
        for row in raw_rows:
            if row["video_id"] in seen_video_ids:
                continue
            seen_video_ids.add(row["video_id"])
            rows.append(row)

        # Minimum-views guard: under-exposed videos have meaningless ratios
        eligible_rows = [r for r in rows if (r["views"] or 0) >= MIN_VIEWS_FOR_LEARNING]
        skipped_low_views = len(rows) - len(eligible_rows)
        if skipped_low_views:
            log.info(
                f"[SAMPLE GUARD] {skipped_low_views} video(s) below {MIN_VIEWS_FOR_LEARNING} views — "
                "excluded from learning (ratios not yet meaningful)."
            )
        rows = eligible_rows
        if not rows:
            log.info("No eligible analytics observations after sample guards. No weight updates applied.")
            return

        # Group observations by weight key to check sample_count before updating
        pending_updates: Dict[str, List[float]] = {}
        score_log = []

        for row in rows:
            hook_type = row["hook_type"]
            cluster = row["cluster"]
            views = max(1, row["views"])
            likes_rate = row["likes"] / views
            subs_rate = row["subscribers_gained"] / views

            score = compute_shorts_performance_score(
                viewed_pct=row["viewed_vs_swiped_pct"],
                apv_pct=row["avg_percentage_viewed"],
                likes_per_view=likes_rate,
                subs_per_view=subs_rate,
                # has_independent_hook_signal=False: YouTube Analytics API v2 does not
                # provide a separate Shorts swipe rate. hook_weight is absorbed into
                # retention_weight to avoid double-counting averageViewPercentage.
                # Set to True when a real, API-distinct swipe metric is available.
                has_independent_hook_signal=False
            )

            # Adjustment delta: baseline 0.70 score has 0 delta. Above 0.70 boosts weight.
            delta = round((score - 0.70) * 0.25, 4)
            score_log.append({
                "video": row["video_title"][:40],
                "hook": hook_type,
                "cluster": cluster,
                "score": score,
                "delta": delta,
                "recorded_at": row["recorded_at"]
            })

            if hook_type:
                pending_updates.setdefault(f"hook:{hook_type}", []).append(delta)
            if cluster:
                pending_updates.setdefault(f"cluster:{cluster}", []).append(delta)

    # Check current sample counts and only update keys with enough observations
    for weight_key, deltas in pending_updates.items():
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT weight_value, sample_count FROM dynamic_weights WHERE weight_key = ?",
                (weight_key,)
            )
            existing = cursor.fetchone()
            current_samples = existing["sample_count"] if existing else 0

        total_samples_after = current_samples + len(deltas)
        avg_delta = sum(deltas) / len(deltas)

        if total_samples_after < min_samples:
            log.info(
                f"[WEIGHT HOLD] '{weight_key}': {total_samples_after}/{min_samples} samples — "
                f"bootstrap threshold not yet met. Delta {avg_delta:+.4f} queued but not applied."
            )
            continue

        update_weight(weight_key, avg_delta)
        log.info(
            f"[WEIGHT UPDATE] '{weight_key}': delta {avg_delta:+.4f} "
            f"(based on {len(deltas)} observations, {total_samples_after} total samples, "
            f"window: {window_days}d). Scores: {[s['score'] for s in score_log if s.get('hook') == weight_key.split(':')[-1] or s.get('cluster') == weight_key.split(':')[-1]]}"
        )

    log.info(f"Decision engine weight adjustments completed. {len(pending_updates)} keys evaluated.")
