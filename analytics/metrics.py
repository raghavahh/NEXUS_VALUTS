"""
NEXUS VAULTS 2.0 - Analytics Metrics & Scoring Formula

HONEST SIGNAL MODEL:
  YouTube Analytics API v2 provides ONE retention signal: averageViewPercentage (APV).
  There is no separate Shorts "swipe-through rate" in the public API.

  Giving APV a 35% hook_weight AND a 35% retention_weight means 70% of the score
  comes from a single underlying metric — the two signals are not independent.

  This is fixed by:
  - When has_independent_hook_signal=False (default, current API state):
    retention_weight absorbs the hook_weight entirely (hook_weight -> 0)
    Effective formula: APV × 0.70 + Engagement × 0.15 + Subs × 0.15
  - When has_independent_hook_signal=True (future: real Shorts swipe rate available):
    hook_weight and retention_weight operate independently as configured

  Formula weights are configurable via .env. These are bootstrap heuristics;
  recalibrate after ANALYTICS_MIN_SAMPLE_COUNT videos have been published.
"""

from core.config import config


def compute_shorts_performance_score(
    viewed_pct: float,
    apv_pct: float,
    likes_per_view: float,
    subs_per_view: float,
    has_independent_hook_signal: bool = False
) -> float:
    """
    Computes weighted content performance score.

    Args:
        viewed_pct:                 Hook hold rate (viewed vs. swiped %). Currently same
                                    as apv_pct because no separate swipe metric exists in
                                    YouTube Analytics API v2.
        apv_pct:                    Average percentage viewed (retention signal from API).
        likes_per_view:             Likes / views ratio.
        subs_per_view:              Subscribers gained / views ratio.
        has_independent_hook_signal: True only when a REAL, API-distinct hook metric
                                    (e.g., Shorts swipe rate) is available. Default False.
                                    When False, hook weight is collapsed into retention
                                    weight to avoid double-counting APV.

    Returns:
        Performance score in range [0.0, ~1.2].
    """
    w_retention = config.analytics.score_weight_retention
    w_engagement = config.analytics.score_weight_engagement
    w_subs = config.analytics.score_weight_subs

    if has_independent_hook_signal:
        # Two genuinely independent signals — use hook weight separately
        w_hook = config.analytics.score_weight_hook
        hook_signal = min(1.0, viewed_pct / 100.0)
    else:
        # No separate hook signal — collapse hook weight into retention to avoid double-counting
        # Effective: retention absorbs the hook weight (0.35 + 0.35 = 0.70 of APV)
        w_hook = 0.0
        hook_signal = 0.0
        w_retention = w_retention + config.analytics.score_weight_hook  # absorb hook weight

    retention_signal = min(1.2, apv_pct / 100.0)   # 1.2 cap rewards exceptional watch-through
    engagement_signal = min(1.0, likes_per_view * 20.0)
    sub_signal = min(1.0, subs_per_view * 100.0)

    score = (
        hook_signal * w_hook +
        retention_signal * w_retention +
        engagement_signal * w_engagement +
        sub_signal * w_subs
    )
    return round(score, 3)
