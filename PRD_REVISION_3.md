# NEXUS VAULTS 2.0 — Full Product Requirements Document (PRD)
### A-to-Z Technical & Operational Reference · Revision 3

> **Version:** Production Release v2 · **PRD Revision:** 3 · **Channel:** @NEXUS_VAULTS · **Stack:** Python 3.11+

---

## Consistency Audit: All Issues Resolved (Rev 1 + Rev 2 Review)

> [!IMPORTANT]
> Rev 2 fixed 12 contradictions. Rev 3 resolves the 6 remaining issues from the second review.

### Rev 3 Fixes (this version)

| # | Issue | Resolution |
|---|-------|----------|
| R2-1 | `--upload` could override `APP_MODE` gate | `--upload` removed entirely. Upload gated solely by `APP_MODE=production` in `.env`. |
| R2-2 | "Source traceability" had no actual claim verification | New `content/claim_verifier.py` — step 5.5 audits every narration sentence against Wikipedia source before scene planning. Unsupported claims → regenerate or defer. |
| R2-3 | `viewed_vs_swiped_pct` appeared in architecture but wasn't honestly defined | Removed fake `avg_pct * 1.2` estimate. `hook_hold_rate_pct = avg_percentage_viewed` (single source, two semantic roles). Documented clearly. |
| R2-4 | Learning system language implied deep behavioral intelligence | PRD now explicitly describes it as an explainable, bounded adaptive heuristic. |
| R2-5 | Pexels had no purpose-level restriction | Pexels blocked from all primary-evidence purposes (`SHOW_PRIMARY_EVIDENCE`, `IDENTIFY_PERSON`, `EXPLAIN_MECHANISM`, etc.). Allowed for atmosphere/context only. |
| R2-6 | Obscure topic edge case — might manufacture visual diversity | Documented: if < 4 authentic assets found for a topic, system defers that scene to generated graphic (if contract allows) or aborts — never reuses assets or fakes diversity. |

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Directory Structure](#3-directory-structure)
4. [Pipeline Execution Flow (A–Z)](#4-pipeline-execution-flow-a-z)
5. [Module-by-Module Deep Dive](#5-module-by-module-deep-dive)
6. [Database Schema](#6-database-schema)
7. [Deduplication System](#7-deduplication-system)
8. [Relevance Gate](#8-relevance-gate)
9. [QC Gate System](#9-qc-gate-system)
10. [Publishing & Scheduling Logic](#10-publishing--scheduling-logic)
11. [Self-Learning Feedback Loop](#11-self-learning-feedback-loop)
12. [Configuration Reference](#12-configuration-reference)
13. [CLI Usage & Flags](#13-cli-usage--flags)
14. [Data Lifecycle & Storage Policy](#14-data-lifecycle--storage-policy)
15. [Production Rules (Non-Negotiable)](#15-production-rules)
16. [Golden Regression Test Standard](#16-golden-regression-test-standard)

---

## 1. Product Vision

NEXUS VAULTS 2.0 is a **fully autonomous YouTube Shorts documentary engine**. It requires zero human intervention from idea to published video. Every day it:

1. **Discovers** a real, **not previously published by NEXUS VAULTS**, historical or scientific topic from Wikipedia
   *(Note: the system guarantees novelty within its own topic registry — it cannot guarantee global uniqueness across all YouTube channels)*
2. **Scripts** a 30–40 second documentary narration with a cinematic hook
3. **Plans** 10–15 scenes with strict claim-local visual assignments
4. **Harvests** authentic archival images from Wikimedia Commons / Wikipedia
5. **Renders** a 1080×1920 documentary Short with kinetic captions, motion, and EBU R128–mastered audio
6. **Verifies** output through a 3-layer (L1/L2/L3) visual QC pipeline — all 3 layers at 100%
7. **Schedules** the upload to YouTube at 7:00 PM ET the following day
8. **Records** source-backed performance metrics and feeds them back to improve future videos

**Hard rules (non-negotiable):**
- Zero duplicate topics (exact duplicates and same-angle repeats rejected; same subject + new evidence allowed)
- Zero filler / placeholder visuals — every scene must satisfy a claim-level visual contract
- **No hardcoded secrets, operational config, or tunable thresholds** — those live in `.env`. Algorithm invariants (delta formula, overlap thresholds, score bounds) are source code constants, which is correct and intentional. The rule is not "every integer in the codebase must be an env var."
- Video must be ready ≥ 1 hour before scheduled publication; if not, status = DEFERRED
- Upload is always `privacyStatus=private` + `publishAt` — never goes live immediately
- Upload requires `APP_MODE=production`. No CLI flag can bypass this.
- Own-channel analytics = YouTube Analytics API v2 only. yt-dlp is never a channel analytics fallback.
- LLM output is grounded in Wikipedia facts; claim traceability (not zero hallucination) is the guarantee

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    NEXUS VAULTS 2.0                          │
│              Autonomous YouTube Shorts Engine                │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │         main.py (Orchestrator)       │
        │   25-step linear production pipeline │
        └──────────────────┬──────────────────┘
                           │
     ┌─────────────────────┼──────────────────────┐
     │                     │                       │
     ▼                     ▼                       ▼
 RESEARCH             CONTENT                    MEDIA
 discover.py          hooks.py                 images.py
 growth_brain.py      story_brain.py           voice.py
 yt_intel.py*         scene_planner.py         captions.py
  (*competitors only) seo.py                   audio_bed.py
                                               compositor.py
                                               explanatory_graphic.py

OWN CHANNEL ANALYTICS:                 COMPETITOR INTELLIGENCE:
YouTube Analytics API v2               yt-dlp / public Data API
(authenticated OAuth)                  (research/yt_intel.py only)
```

---

## 3. Directory Structure

```
c:\YT-SHORTS\
├── .env                        ← Single source of truth (all secrets + runtime config)
├── .env.example                ← Template (18 config sections)
├── main.py                     ← 25-step orchestrator
├── nexus.db                    ← SQLite persistent state
│
├── core/
│   ├── config.py               ← 17 frozen dataclasses (incl. AnalyticsConfig)
│   ├── database.py             ← 6 tables + CRUD + 3-level novelty audit
│   ├── llm_router.py           ← 4-provider cloud chain
│   ├── manifest.py             ← Immutable render manifest
│   └── scheduler.py            ← US-timezone scheduling + gap + readiness gate
│
├── research/
│   ├── discover.py             ← Wikipedia crawler (defers on empty — no hardcoded fallbacks)
│   ├── growth_brain.py         ← LLM topic selector
│   └── yt_intel.py             ← Competitor intelligence (public yt-dlp — NOT own channel)
│
├── content/
│   ├── hooks.py               ← Hook generation + scoring
│   ├── story_brain.py         ← Narration script generation (strict_source_grounding support)
│   ├── claim_verifier.py      ← Step 5: Claim Verification Gate (Wikipedia source audit)
│   ├── scene_planner.py       ← Step 8: Claim-local visual assignment
│   └── seo.py                 ← Step 6: SEO packaging (runs AFTER claim verification)
├── media/                      ← images → explanatory_graphic → voice → captions → audio_bed → compositor
├── qc/                         ← frame_verifier (L1+L2+L3 all at 100%) → contact_sheet
├── publisher/youtube.py        ← OAuth2 resumable upload + scheduled publish
│
└── analytics/
    ├── sync.py                 ← YouTube Analytics API v2 (own channel, authenticated)
    ├── decision_engine.py      ← Feedback loop with sample_count guard + observation window
    └── metrics.py              ← Configurable score formula (weights from .env)
```

---

## 4. Pipeline Execution Flow (A–Z)

| Step | Module | Action |
|------|--------|--------|
| 0 | `core/config.py` | `config.validate()` — fail fast if no AI key |
| 1 | `core/database.py` | `init_db()` — 6 tables, seed weights, `get_next_file_number()` |
| **2** | `analytics/sync.py` | **`sync_channel_analytics()`** — YouTube Analytics API v2 (own channel). Decision engine updates weights for the **next run** using **previous runs' data**. |
| 3 | `research/discover.py` | `discover_candidates()` — Wikipedia crawler, defers if empty |
| 3b | `research/growth_brain.py` | `produce_growth_brain()` — LLM topic selection + 3-level novelty audit |
| 3c | `core/database.py` | `record_topic()` → topics table |
| 4 | `content/hooks.py` | `generate_and_score_hooks()` — 10 candidates, dynamic weight scoring |
| **5** | `content/story_brain.py` | `generate_production_script()` — 68–84 word narration |
| **5 (gate)** | `content/claim_verifier.py` | **`verify_script_claims()`** — audits every sentence against Wikipedia source. UNSUPPORTED → regenerate (once) or defer. Runs BEFORE SEO. |
| **6** | `content/seo.py` | `format_seo_package()` — runs AFTER narration is verified and finalized |
| 7 | `media/voice.py` | `generate_voice()` — edge-tts + word-level timecodes |
| **8** | `content/scene_planner.py` | `generate_storyboard()` — 10–15 claim-local scenes |
| 9 | `media/images.py` | `collect_storyboard_assets()` — per-scene harvest, authentic sources exhausted before GENERATED_GRAPHIC |
| 9b | `main.py` | `assert` unique canonical URLs + unique SHA-256 across all scenes |
| 10 | `media/captions.py` | `generate_kinetic_ass()` — word-synced ASS subtitle |
| 11 | `media/audio_bed.py` | Ambient drone + EBU R128 mastering (−14 LUFS) |
| 12 | `core/manifest.py` | `generate_render_manifest()` — immutable scene→asset binding |
| 13 | `media/compositor.py` | `build_composite_video_from_manifest()` — FFmpeg |
| 14 | `main.py` | `assert` final MP4 duration 29.5s–40.5s |
| 15 | `qc/frame_verifier.py` | `verify_scene_clips_and_frames()` — **L1=100%, L2=100%, L3=100%** |
| 16 | `qc/contact_sheet.py` | `generate_contact_sheet()` |
| 17 | `core/scheduler.py` | `get_schedule_window()` + `evaluate_readiness_guarantee()` |
| 18 | `publisher/youtube.py` | `upload_short_to_youtube()` — private + `publishAt` tomorrow 7PM ET |
| 19 | `core/database.py` | `record_video()` + `record_provenance()` |
| 20 | `core/database.py` | `record_content_memory()` — lightweight (≤300 char summary, no media) |
| 21 | `main.py` | `cleanup_intermediate_files()` |
| 22 | `core/state_store.py` | `save_state()` |
| 23 | `media/images.py` | `format_relevance_report()` — per-scene breakdown to console |
| 24 | `main.py` | Full structured production report (single source of truth: current `file_number`) |

> **Ordering note:** The decision engine at step 2 reads and learns from *previously published* videos. The current run's data will be learned at step 2 of the *next* run.

---

## 5. Module-by-Module Deep Dive

### 5.1 Configuration Layer
**File:** [`core/config.py`](file:///c:/YT-SHORTS/core/config.py)

**17 config groups** — all frozen dataclasses, all read from `.env`:

| Config Group | Key Fields |
|-------------|-----------|
| `AppConfig` | env, mode (`production`\|`test`), debug |
| `AIConfig` | provider_chain, all 4 API keys + models |
| `YouTubeConfig` | OAuth credentials, category_id, privacy, quota limits |
| `MediaConfig` | pexels_api_key |
| `ResearchConfig` | max_topics, content_pillars |
| `StoryConfig` | target_duration, min/max words |
| `HookConfig` | candidate_count, min_score |
| `SceneConfig` | min/target/max_count, `DEDUP_HAMMING_THRESHOLD` (unified) |
| `RenderConfig` | 1080×1920, 30fps, libx264, CRF 20 |
| `AudioConfig` | voice, rate, pitch, loudnorm settings |
| `CaptionConfig` | font, font_size, words_per_line |
| `SEOConfig` | title/desc/tag limits |
| `QCConfig` | duration bounds, frame verification thresholds |
| `StorageConfig` | output_dir, temp_dir, db_path, cleanup flags |
| `ScheduleConfig` | timezone, upload_hour, gap, buffer |
| `TestConfig` | test_mode, skip_upload (test-only), keep_artifacts |
| **`AnalyticsConfig`** | **score weights (hook/retention/engagement/subs), min_sample_count, observation_window_days** |

---

### 5.2 Analytics Config (new — fix #11)
```
ANALYTICS_SCORE_WEIGHT_HOOK=0.35       # bootstrap heuristic — recalibrate
ANALYTICS_SCORE_WEIGHT_RETENTION=0.35
ANALYTICS_SCORE_WEIGHT_ENGAGEMENT=0.15
ANALYTICS_SCORE_WEIGHT_SUBS=0.15
ANALYTICS_MIN_SAMPLE_COUNT=3           # weight updates held until this many samples
ANALYTICS_OBSERVATION_WINDOW_DAYS=90   # stale data excluded from weight changes
```

These are configurable heuristics, not facts. As sample count grows beyond `min_sample_count`, the engine re-weights clusters and hooks. The formula will never be silently hardcoded.

---

### 5.3 Own-Channel Analytics Architecture (fix R1-1, R1-2)

```
OWN CHANNEL METRICS (private, authenticated)
        │
        ▼
YouTube Analytics API v2
(youtubeanalytics.googleapis.com/v2/reports)
        │
        ├── views, likes, comments
        ├── averageViewPercentage  ← sole retention signal from API
        ├── averageViewDuration
        └── subscribersGained

HOOK HOLD RATE: hook_hold_rate_pct = averageViewPercentage
  (no separate Shorts swipe metric exists in Analytics API v2)
  This is the single metric used for both the hook_signal and retention_signal
  in the scoring formula — they come from the same API field.
  If YouTube ever exposes a Shorts-specific swipe rate, it will be added here.

REMOVED: estimated_viewed_vs_swiped_pct = avg_pct × 1.2
  That was a circular heuristic creating a fake second signal from the same data.

COMPETITOR INTELLIGENCE (public only)
        │
        ▼
research/yt_intel.py  ← yt-dlp / public Data API
                         NEVER touches own-channel data

OWN CHANNEL FALLBACK: If OAuth fails → WARNING logged → sync skipped.
yt-dlp is NOT invoked as own-channel fallback.
```

---

### 5.4 Claim Verification Gate (new — fix R2-2)
**File:** [`content/claim_verifier.py`](file:///c:/YT-SHORTS/content/claim_verifier.py)

Sits between **Step 5** (script generation) and **Step 8** (scene planning). Closes the gap between source traceability and actual claim verification.

**Flow:**
```
Wikipedia article text  +  Generated narration
              │
              ▼
  Single LLM call — one audit per run (not one per sentence)
              │
              ▼
  Per-sentence verdicts:
    SUPPORTED           → directly traceable to source
    PARTIALLY_SUPPORTED → implied/generalized from source
    UNSUPPORTED         → not in source (hallucination risk)
              │
              ▼
  PASS: unsupported_count ≤ 0, partial_count ≤ 3
  FAIL: → attempt one regeneration with strict_source_grounding=True
           → if still failing → pipeline DEFERRED (no video published)
```

**What this adds:** The traceability chain is now:
```
Wikipedia → Extracted Facts → LLM Script
                                  │
                     Claim Verification Gate ←── catches invented dates,
                                  │               fabricated causality,
                                  ▼               distorted facts
                           Visual Assignment → Asset
```

**Limitation acknowledged:** This is an LLM-audits-LLM check. It is materially stronger than no verification, but is not a formal proof-of-correctness. The system reports source-backed claims, not guaranteed factual accuracy.

---

### 5.5 Self-Learning System — Honest Description (fix R2-4)

The decision engine is an **explainable, bounded adaptive heuristic** — not a deep learning or behavioral intelligence system.

```
Score formula:  configurable weights (hook/retention/engagement/subs)
Weight update:  delta = (score − 0.70) × 0.25
Bounds:         weight ∈ [0.2, 3.0]
Bootstrap:      no updates until min_sample_count reached
Window:         only last observation_window_days of data used
Explainability: every update logged with delta, sample_count, score basis
```

This is a simple performance-weighted hill-climber. It is useful precisely because it is explainable and auditable. Do not represent it as a learning model.

---

### 5.6 Authentic-Source Exhaustion + Pexels Rules (fix R2-5, R2-6)

**Tier hierarchy (authentic sources exhausted before generated graphics):**
```
Tier 1: Wikipedia Article Media (embedded images in the source article)
Tier 2: Wikimedia Commons Search (3 ranked archival queries)
Tier 3: Pexels — ATMOSPHERIC + non-evidence purposes ONLY
Tier 4: Explanatory Graphic (GENERATED_GRAPHIC) — last resort
```

**Pexels hard rule:**
```python
PEXELS_BLOCKED_PURPOSES = {
    "SHOW_PRIMARY_EVIDENCE", "SHOW_SECONDARY_EVIDENCE", "IDENTIFY_PERSON",
    "HIGHLIGHT_DETAIL", "REVEAL_INFORMATION", "SHOW_ROUTE",
    "SHOW_TIMELINE", "SHOW_CONTRADICTION", "EXPLAIN_MECHANISM"
}
# Pexels only serves: ESTABLISH_LOCATION, PROVIDE_CONTEXT, BUILD_TENSION
# AND only when visual_type == ATMOSPHERIC
```

**Obscure topic edge case (fix R2-6):**
If a topic has fewer than 4 usable authentic images:
- Scenes with `ATMOSPHERIC`, `CONTEXT`, `TIMELINE` visual_type → may use generated graphic
- Scenes with `SHOW_PRIMARY_EVIDENCE`, `IDENTIFY_PERSON` → pipeline defers the scene
- The system NEVER reuses assets or manufactures visual diversity to hit the 10–15 count
- If the count falls below `SCENE_MIN_COUNT` and cannot be resolved → run is deferred

---

### 5.4 Topic Novelty System (fix #9)

Three distinct rejection levels:

| Level | Trigger | Result |
|-------|---------|--------|
| **EXACT DUPLICATE** | Same normalized title / topic key | Always reject |
| **SAME ANGLE** | Summary overlap > 60% AND title token overlap ≥ 40% | Reject |
| **SAME SUBJECT, NEW EVIDENCE** | Title tokens overlap ≥ 40% BUT summary overlap < 55% | **Allowed** |

Example of correctly allowed story:
```
Story A: "Mary Celeste — crew disappearance mystery" (abandonment angle)
Story B: "Newly decoded Mary Celeste logbook page reveals storm damage" (new evidence angle)
→ ALLOWED — genuinely different narrative despite shared subject
```

---

### 5.5 Asset Deduplication (fix #8, #10)

**The dedup requirement is asset-based, not concept-based.**

The production requirement is:
- **Zero accidental asset reuse** — no two scenes share the same image file (URL/SHA/dHash)
- Scenes **may** legitimately revisit the same conceptual subject (e.g., Hawking in scene 1 and scene 7) as long as they use different authentic assets

**Unified threshold:** `DEDUP_HAMMING_THRESHOLD=6` (one .env key, governs everything)
- `IMAGE_DEDUP_HAMMING_THRESHOLD` is a legacy alias that maps to the same value

**5-Tier dedup waterfall** (unchanged except for title tier clarification):

| Tier | Hard Reject? |
|------|-------------|
| 1. Canonical URL | ✅ Yes |
| 2. SHA-256 binary | ✅ Yes |
| 3. dHash Hamming ≤ threshold | ✅ Yes |
| 4. Crop-aware similarity | ✅ Yes |
| 5. Normalized title | ❌ No — supporting signal only |

---

### 5.6 QC Gate (fix #7)

**All three layers must be 100% for all scenes:**

```
L1: Every scene clip exists + size > 1KB + source asset on disk   → 100% required
L2: dHash(clip_mid_frame) vs dHash(source_asset) ≥ 0.40 ratio     → 100% required
L3: dHash(clip_frame) vs dHash(final_mp4_at_ts) Hamming ≤ 20     → 100% required
```

Previous behavior (L2 at 85%) is removed. Any L2 failure is a hard QC block.

---

### 5.7 Relevance Gate (fix #6 — claim traceability, not zero hallucination)

Every asset is scored on 8 dimensions. If the required dimensions for the visual_type fail, the asset is rejected.

The system's claim to factual integrity is:
- **Facts are sourced from Wikipedia REST API** (traceable to a specific article)
- **The LLM receives those facts as grounding context** when generating the script
- **The relevance gate verifies that the visual matches the specific claim** in the narration

**The system does NOT claim zero hallucination.** The LLM may still misinterpret, combine, or incorrectly phrase source material. The traceability chain is:
```
Wikipedia Article → Extracted Facts → LLM Script → Claim → Visual Assignment → Asset
```
Not: `Guaranteed factually perfect output`

---

### 5.8 Authentic-Source Exhaustion Before Generated Graphics (PRD §13 addendum)

The image harvester **must** exhaust all authentic candidates before invoking the graphic generator:

```
Wikipedia Article Images
        ↓ (if no candidate passes relevance gate)
Wikimedia Commons Search (3 ranked archival queries)
        ↓ (if still no valid candidate)
Pexels API (atmospheric/cinematic only, if key set)
        ↓ (if ALL above fail relevance gate)
Explanatory Graphic (GENERATED_GRAPHIC) — last resort only
```

Generated graphics are logged as `source: NEXUS_GENERATED`. A run with more than 3 generated graphics out of 12 scenes should trigger a relevance gate calibration review.

**Generated asset identity model:**
```
AUTHENTIC asset:          GENERATED asset (nexus-generated://):
  canonical_url = https://…  canonical_url = nexus-generated://nexus_graphic_{scene_id}_{claim_hash}
  url           = https://…  url           = file://{local_output_path}  (FFmpeg access)
  sha256        = content ✓  sha256        = content ✓
  dhash         = visual  ✓  dhash         = visual  ✓
```

The `nexus-generated://` scheme is a stable, unique identifier. It satisfies the canonical URL uniqueness assertion without inventing fake HTTP URLs. The `scene_id` + `claim_hash` pair guarantees no two scenes share the same identity even if they contain similar diagrams. `sha256` and `dhash` still provide binary and perceptual uniqueness respectively.

---

## 6. Database Schema

*(unchanged from Revision 1 — see previous PRD for full SQL)*

---

## 7. Deduplication System

*(see §5.5 above — unified threshold, asset-based not concept-based)*

---

## 8. Relevance Gate

*(see §5.7 above — source-backed traceability, not zero hallucination)*

---

## 9. QC Gate System

*(see §5.6 above — L1=100%, L2=100%, L3=100%)*

---

## 10. Publishing & Scheduling Logic

```
RENDER COMPLETE
      │
      ▼
get_schedule_window(target_tomorrow=True)
      │
      ├─ Target: tomorrow at SCHEDULE_UPLOAD_HOUR (default 19:00 ET)
      ├─ Enforce: last_upload + MIN_UPLOAD_GAP_HOURS (≥18h)
      └─ ready_by_deadline = target_upload − 60 minutes
      │
      ▼
evaluate_readiness_guarantee(qc_passed=True)
      │
      ├─ current_time < ready_by_deadline → READY
      └─ current_time > ready_by_deadline → DEFERRED_PAST_DEADLINE
      │
      ▼  (READY + APP_MODE=production + not skip_upload)
upload_short_to_youtube(publish_at=ISO-UTC)
    → privacyStatus="private" + publishAt
    → post-upload API verification
```

**Removed:** `--force-publish` flag. The 1-hour readiness guarantee is non-negotiable.
**Removed from production gate:** `TEST_SKIP_UPLOAD`. Only `APP_MODE` governs upload.

---

## 11. Self-Learning Feedback Loop

```
STEP 2 OF NEXT RUN → reads analytics from previously published videos
        │
        ▼
YouTube Analytics API v2 (authenticated)
    views / averageViewPercentage / likes / subs
        │
        ▼
compute_shorts_performance_score()
    Weights from config.analytics (configurable heuristics)

    ┌──────────────────────────────────────────────────────────────┐
    │ has_independent_hook_signal = False  (current API state)          │
    │                                                                  │
    │ YouTube Analytics API v2 does not expose a separate Shorts       │
    │ swipe-through rate. averageViewPercentage (APV) is the only      │
    │ retention-related signal available. Giving APV both a hook       │
    │ weight AND a retention weight would double-count the same        │
    │ metric. Instead, hook_weight is COLLAPSED into retention_weight: │
    │                                                                  │
    │   effective_hook_weight      = 0.00                              │
    │   effective_retention_weight = hook_w + retention_w = 0.70      │
    │   effective_engagement_weight = 0.15                            │
    │   effective_subs_weight       = 0.15                            │
    │                                                                  │
    │   score = APV × 0.70 + Likes × 0.15 + Subs × 0.15             │
    ├──────────────────────────────────────────────────────────────┤
    │ has_independent_hook_signal = True  (future: real swipe data)    │
    │                                                                  │
    │ When YouTube exposes a Shorts-specific swipe metric, set this    │
    │ flag to True and hook_weight applies independently:             │
    │                                                                  │
    │   score = HookRate × 0.35 + APV × 0.35 + Likes × 0.15 + Subs × 0.15 │
    └──────────────────────────────────────────────────────────────┘
        │
        ▼
delta = (score − 0.70) × 0.25
        │
        ▼
Check: current_sample_count + new_samples >= ANALYTICS_MIN_SAMPLE_COUNT?
    NO  → Weight held. Logged but not applied (bootstrap guard).
    YES → update_weight(key, avg_delta) — bounded [0.2, 3.0]
        │
        ▼
Every update logged with: key, delta, sample_count, observation_window, score basis
```

**Ordering clarity (fix #12):** The decision engine at step 2 operates on *previous* runs' data. The current run's analytics are not yet available. The system never claims to have learned from data it hasn't observed.

---

## 12. Configuration Reference

| Section | Key Parameters |
|---------|---------------|
| **AI** | `AI_PROVIDER_CHAIN=openrouter,groq,nvidia,gemini` |
| **YouTube** | `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` |
| **Story** | `STORY_TARGET_DURATION=36`, `STORY_MIN_WORDS=68`, `STORY_MAX_WORDS=84` |
| **Scenes** | `SCENE_MIN_COUNT=10`, `SCENE_TARGET_COUNT=12`, `SCENE_MAX_COUNT=15` |
| **Dedup** | `DEDUP_HAMMING_THRESHOLD=6` ← **one key only** |
| **Render** | `RENDER_WIDTH=1080`, `RENDER_HEIGHT=1920`, `RENDER_FPS=30` |
| **Audio** | `AUDIO_LOUDNORM_I=-14.0` (EBU R128) |
| **Scheduling** | `SCHEDULE_TIMEZONE=America/New_York`, `SCHEDULE_UPLOAD_HOUR=19`, `MIN_UPLOAD_GAP_HOURS=18` |
| **Analytics (new)** | `ANALYTICS_SCORE_WEIGHT_HOOK=0.35`, `ANALYTICS_MIN_SAMPLE_COUNT=3`, `ANALYTICS_OBSERVATION_WINDOW_DAYS=90` |
| **Mode** | `APP_ENV=production`, `APP_MODE=production` |
| **Test** | `TEST_SKIP_UPLOAD=true` ← test-only, never controls production upload |

---

## 13. CLI Usage & Flags

```bash
# Full production run (upload only if APP_MODE=production in .env)
python main.py

# Research + storyboard plan only — no render, no upload
python main.py --dry-run

# Render video locally, skip YouTube upload even if APP_MODE=production
python main.py --skip-upload

# Force a specific topic (bypasses Wikipedia discovery)
python main.py --force-topic "Mary Celeste"
```

**Upload gate — one rule only:**
```
UPLOAD EXECUTES IF AND ONLY IF:
  APP_MODE == "production"    (set in .env)
  AND skip_upload == False    (not passed as CLI flag)
  AND readiness == READY      (1-hour buffer satisfied)
  AND QC == PASS              (L1 + L2 + L3 all 100%)

There is no CLI flag that can bypass APP_MODE.
Setting APP_MODE=production IS the production authorization.
```

**Removed flags:**
- `--upload` — removed. Was a leftover that could override the production gate.
- `--force-publish` — removed. The 1-hour readiness guarantee cannot be bypassed.

---

## 14. Data Lifecycle & Storage Policy

| Data | Permanent? | Location |
|------|-----------|---------|
| Final MP4 | ✅ Yes | `OUTPUT/FILE_NNN_nexus_short.mp4` |
| Contact Sheet | ✅ Yes | `OUTPUT/FILE_NNN_contact_sheet.png` |
| SQLite DB | ✅ Yes | `nexus.db` |
| Topic, video, provenance, analytics, weights, memory | ✅ Yes | SQLite tables |
| Voice MP3, ambient, mixed audio, ASS captions | ❌ Temp | `OUTPUT/temp/` → deleted |
| Scene clips, render manifest | ❌ Temp | `OUTPUT/temp/scenes_NNN/` → deleted |
| Downloaded images | ❌ Temp | `OUTPUT/FILE_NNN_assets/` → deleted |

---

## 15. Production Rules

1. `APP_MODE=production` + `skip_upload=False` is the only path to YouTube upload.
2. `TEST_SKIP_UPLOAD` has no effect on production behavior.
3. `--force-publish` does not exist. The 1-hour deadline is enforced by code.
4. All research must be dynamically discovered. No hardcoded topic lists exist in the codebase.
5. Own-channel analytics = YouTube Analytics API v2 (authenticated). Not yt-dlp.
6. yt-dlp = public competitor intelligence only (`research/yt_intel.py`).
7. Minimum 18 hours between uploads. Scheduler auto-advances if gap is not met.
8. L1=L2=L3=100% for all scenes. Partial QC pass blocks upload.
9. Duplicate upload protection: if `youtube_video_id` exists for `file_number`, skip upload.
10. Topic novelty: exact duplicates + same-angle stories are rejected. Same subject + new evidence is allowed.
11. Analytics weight updates are held until `min_sample_count` is reached per key (bootstrap guard).
12. Generated graphics are a last resort. Authentic archival sources are exhausted first.
13. Every production report section is generated from the current `file_number` only. No stale data.
14. The claim traceability chain (Wikipedia → Facts → Script → Scene → Asset) is maintained but does not guarantee zero hallucination.

---

## 16. Golden Regression Test Standard

A run passes the Golden Regression Test when:

```
✅ 10–15 distinct scene claim subjects (claim-local, not topic-level)
✅ 10–15 unique canonical asset URLs (zero asset reuse)
✅ 10–15 unique SHA-256 binary hashes
✅ 0 dHash perceptual duplicates (all pairs Hamming > DEDUP_HAMMING_THRESHOLD)
✅ Final video duration: 29.5s ≤ d ≤ 40.5s
✅ L1=100%, L2=100%, L3=100% (all scenes, all layers)
✅ No black frames in any scene
✅ Topic passes 3-level novelty audit (exact dup check, same-angle check)
✅ Generated graphics ≤ 3 of 12 scenes (else relevance gate review required)
✅ Upload status = SCHEDULED (private + publishAt set)
✅ publishAt ≥ 18h after last upload, at SCHEDULE_UPLOAD_HOUR ET
✅ Exactly one youtube_video_id per file_number in the database and production report
✅ Analytics weights only updated if sample_count ≥ ANALYTICS_MIN_SAMPLE_COUNT
```

The **original failure case** (one image rendered for 40 seconds):
1. Fails Tier 1 dedup — same canonical URL
2. Fails Tier 2 dedup — same SHA-256
3. Fails `assert len(unique_urls) == len(scenes)` in `main.py`
4. Pipeline aborts before rendering

**Regression prevented. Test fails. Pipeline never silently ships the broken output.**

---

*NEXUS VAULTS 2.0 PRD Rev 3 · All 12 Rev 1 contradictions + 6 Rev 2 review issues resolved · Generated by Antigravity IDE*
