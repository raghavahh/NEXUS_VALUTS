# NEXUS VAULTS 2.0 — AUTHORITATIVE PRODUCT REQUIREMENTS DOCUMENT (PRD)
### Autonomous YouTube Shorts Documentary Engine · Production Release v2.0
**Channel:** @NEXUS_VAULTS · **Format:** 1080×1920 Vertical, 30–40s Documentary Shorts  
**Sole Authoritative Technical & Operational Reference**

---

## 1. PRODUCT VISION & IDENTITY CONTRACT

NEXUS VAULTS 2.0 is a **genuinely autonomous, zero-human-intervention documentary production system**. Running on automated cloud schedules, it executes the entire lifecycle of investigative historical and scientific shorts:
1. **Discovers** verifiable, declassified, or anomalous historical/scientific subjects from Wikipedia.
2. **Audits Topic Novelty** across a 3-level persistent registry to eliminate duplicate or same-angle content.
3. **Formulates Retention-Engineered Scripts** (68–84 words, 36.0s target duration) featuring claim-local evidence.
4. **Verifies Every Narration Claim** against primary source texts using automated claim verification before scene planning.
5. **Directs Scene Visuals** with claim-local visual contracts (10–15 scenes), prioritizing authentic archival images (Wikimedia Commons / Wikipedia) over atmospheric visuals (Pexels) or procedural schematics.
6. **Synthesizes Neural Voice & Masters Audio** to strict EBU R128 broadcast standards (-14.0 LUFS ±1.0 LUFS) with dynamic ducking and sub-bass transitions.
7. **Renders Broadcast-Grade Vertical Video** (1080×1920 @ 30fps) via FFmpeg using kinetic ASS typography with word-level highlight sync.
8. **Audits 100% of Rendered Frames** via a 3-layer QC pipeline (L1 existence, L2 perceptual fidelity, L3 composite alignment, plus black/freeze frame detection).
9. **Executes Idempotent Scheduled Uploads** to YouTube with chunked resumable streaming and write-ahead crash safety.
10. **Synchronizes Authoritative Performance Analytics** to adaptively refine topic and hook selection heuristics.

---

## 2. REAL END-TO-END PRODUCTION PIPELINE (25 STEPS)

```
main.py → acquire_production_lock()
       → load_state()                              [state_store.py: persistent SQLite sync]
       → init_db()                                [database.py: WAL mode, timeout=15s]
       → get_incomplete_upload_attempts()          [database.py: idempotency crash recovery guard]
       → get_next_file_number()                    [MAX(file_number)+1: sequential, non-resettable]
       → sync_channel_analytics()                  [analytics/sync.py → YouTube Analytics API v2]
       → process_feedback_loop()                   [analytics/decision_engine.py: bounded weight adjustments]
       → discover_candidates()                     [research/discover.py → Wikipedia category traversal]
       → produce_growth_brain()                    [research/growth_brain.py → LLM narrative angle]
       → verify_topic_novelty()                    [database.py: exact, same-angle, same-subject checks]
       → record_topic()                            [database.py: status='selected']
       → fetch_wikipedia_source_text()             [content/claim_verifier.py: ground-truth extraction]
       → generate_and_score_hooks()                [content/hooks.py: 10 candidates scored against weights]
       → generate_production_script()              [content/story_brain.py: strict word & pacing target]
       → verify_script_claims()                    [content/claim_verifier.py: 0 unsupported claims required]
       → format_seo_package()                      [content/seo.py: archival title, non-spam description]
       → generate_voice()                          [media/voice.py: edge-tts neural synthesis]
       → generate_storyboard()                     [content/scene_planner.py: claim-local entity mapping]
       → collect_storyboard_assets()               [media/images.py: authentic Wikimedia/Pexels harvesting]
       → generate_kinetic_ass()                    [media/captions.py: word-synced amber highlighted ASS]
       → generate_ambient_drone()                  [media/audio_bed.py: atmospheric sub-bass synthesis]
       → mix_and_master_audio()                    [media/audio_bed.py: EBU R128 loudnorm + ducking]
       → generate_render_manifest()                [core/manifest.py: immutable SHA-256 + dHash contract]
       → build_composite_video_from_manifest()     [media/compositor.py: stream-copy / controlled encode]
       → measure_master_loudness()                 [media/audio_bed.py: actual LUFS audit]
       → verify_scene_clips_and_frames()           [qc/frame_verifier.py: L1, L2, L3 100% + freeze/black QC]
       → generate_contact_sheet()                  [qc/contact_sheet.py: rendered frame audit matrix]
       → record_video()                            [database.py: write-ahead row insertion, status='QC_PASSED']
       → mark_upload_attempted()                   [database.py: write-ahead lock prior to network call]
       → upload_short_to_youtube()                 [publisher/youtube.py: chunked resumable PUT, publishAt]
       → update_video_upload()                     [database.py: commit youtube_video_id & status='SCHEDULED']
       → record_content_memory()                   [database.py: lightweight summary for long-term dedup]
       → save_state()                              [core/state_store.py: persistent state branch sync]
       → release_production_lock()
```

---

## 3. SYSTEM CONTRACTS (NON-NEGOTIABLE ARCHITECTURE)

### S1: Channel Identity & Output Specifications
- **Channel Name:** NEXUS VAULTS | **Handle:** @NEXUS_VAULTS
- **Video Dimensions:** 1080 × 1920 (Vertical 9:16 portrait)
- **Target Frame Rate:** 30 fps (libx264, preset fast, CRF 20)
- **Target Audio:** AAC @ 192 kbps, mastered to -14.0 LUFS (±1.0 LUFS tolerance, peak -1.5 dBFS)
- **Sequential File Registry:** Sequential, zero-padded `FILE #001`, `FILE #002`... Never reset or rolled back.
- **Canonical Database:** `nexus.db` (local working tree) synchronized with `.nexus_state/nexus.db` (git-backed persistence).

### S2: Production Scheduling & Readiness Guarantee
- **Target Upload Window:** Next day at 19:00 America/New_York (US Eastern Time).
- **Minimum Upload Spacing:** Minimum 18 hours must separate consecutive uploads. If the gap is violated, the target slot automatically advances by 24 hours.
- **One-Hour Readiness Guarantee:** All rendering and QC must complete at least 60 minutes before the scheduled upload time. If not ready in time, the run safely defers to the next window.
- **Release Mechanism:** YouTube `privacyStatus="private"` coupled with `status.publishAt` UTC ISO-8601 timestamp. The video publishes publicly on YouTube's servers automatically.

### S3: Content Pillars & Topic Clusters
Topics must fall into one of four curated investigative pillars:
1. `Classified History`: Declassified documents, clandestine operations, covert treaties.
2. `Unexplained Events`: Documented maritime/aerial disappearances, unexplainable physical anomalies.
3. `Scientific Mysteries`: Paradoxes in physics, historical laboratory anomalies, unexplained cosmological data.
4. `Strange Real Events`: Bizarre verified historical incidents, lost expeditions, anomalous historical artifacts.

### S4: Unified Cloud AI Routing & Explicit Stable Models
All LLM generation is dynamically dispatched across cloud providers in strict order:
```
NVIDIA NIM → Groq → Gemini → OpenRouter
```
**Model Specifications (Explicit Stable IDs — Zero Floating Aliases):**
- **NVIDIA NIM:** `nvidia/nemotron-3-super-120b-a12b` (Fallback: `meta/llama-3.3-70b-instruct`)
- **Groq:** `qwen/qwen3.8-27b` (Fallbacks: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`)
- **Gemini (Google AI):** `gemini-3.5-flash` (Fallbacks: `gemini-3.6-flash`, `gemini-3.8-flash`)
- **OpenRouter:** `nvidia/nemotron-3-super-120b-a12b:free` (Emergency tertiary fallback)

**Task Specialization Priority:**
- **Primary Generation (Script, Storyboard, Research):** `nvidia → groq → gemini → openrouter`
- **Critic & Hook Architecture:** `nvidia → groq → gemini → openrouter`
- **Fast Formatting & SEO:** `groq → nvidia → gemini → openrouter`

### S5: Documentary Script & Pacing Constraints
- **Target Duration:** 36.0 seconds (Acceptable Range: 30.0s – 40.0s ± 0.5s tolerance).
- **Target Spoken Word Count:** 68 to 84 words.
- **Hook Structure:** Maximum 15 words, single declarative sentence, delivered in the first 0–3 seconds.
- **Fact Verification Gate:** Every narration sentence must be grounded in source Wikipedia text. Maximum 0 unsupported claims, maximum 3 partially-supported claims. If unsupported claims exist, one strict regeneration attempt is executed; if still ungrounded, the pipeline defers immediately.

### S6: Visual Truth & Media Harvesting Rules
- **Minimum Authentic Archival Assets:** ≥ 4 authentic historical images per Short.
- **Maximum Procedural Graphics:** ≤ 3 generated graphics per Short (`source: NEXUS_GENERATED`).
- **Pexels Stock Footage Restrictions:** Pexels is barred from all primary evidence, person identification, or document slots (`SHOW_PRIMARY_EVIDENCE`, `IDENTIFY_PERSON`, `EXPLAIN_MECHANISM`, etc.). Pexels is permitted exclusively for `ATMOSPHERIC` or contextual establishers.
- **Anti-Hallucination Graphic Rule:** Generated schematics may display only confirmed dates, coordinates, and labels derived directly from verified source claims.

### S7: 5-Tier Asset Deduplication Waterfall
Within a Short and across historical registry:
1. **Tier 1 (Canonical URL):** Exact string match reject.
2. **Tier 2 (SHA-256 Binary Hash):** Exact byte hash match reject.
3. **Tier 3 (dHash Perceptual Hash):** Difference hash with Hamming distance threshold `DEDUP_HAMMING_THRESHOLD = 6`.
4. **Tier 4 (Crop-Aware Perceptual Match):** Multi-point quadrant crop matching.
5. **Tier 5 (Normalized Title Token Matching):** Contextual supporting check.

### S8: Quality Control (QC) Gates (100% Pass Required)
1. **Duration Gate:** Measured video duration must be between 29.5s and 40.5s.
2. **Audio Loudness Gate:** Mastered file loudness must be within ±1.0 LU of -14.0 LUFS.
3. **Visual Gate (L1):** 100% of scene video clips exist and are non-empty.
4. **Visual Gate (L2):** 100% of rendered clips match their source image dHash (≥ 0.40 correlation).
5. **Visual Gate (L3):** 100% of composite video sample frames match individual scene clips (Hamming ≤ 20).
6. **Artifact Inspection:** Zero frozen video segments (> 1.5s freeze) and zero black frames (> 0.2s).

### S9: Upload Safety & Idempotency Invariants
- **Write-Ahead Row Insertion:** The database row is committed with `upload_status='QC_PASSED'` before initiating the network upload call.
- **Write-Ahead Attempt Marker:** `mark_upload_attempted(file_number)` is committed immediately before sending video bytes.
- **Duplicate Upload Guard:** If `youtube_video_id` already exists for `file_number`, network upload is immediately blocked.
- **Resumable Chunked Upload:** Uploads proceed in 5 MB chunks with `Content-Range` headers and HTTP 308 resume range handling. No full-file buffering in memory.

### S10: State Synchronization & Lifecycle
- Root database `nexus.db` and cloud backup `.nexus_state/nexus.db` synchronize on every run based on file modification timestamp.
- On completion or failure, temporary scene clips and raw recordings are pruned while broadcast masters and contact sheets are preserved.
- Production lock (`.nexus_state/production.lock`) prevents concurrent runs; stale locks (> 6 hours) automatically recover.

---

## 4. DATABASE SCHEMA REFERENCE

```sql
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster TEXT NOT NULL,
    title TEXT UNIQUE NOT NULL,
    summary TEXT,
    source_url TEXT,
    fact_confidence REAL DEFAULT 0.8,
    demand_score REAL DEFAULT 50.0,
    status TEXT DEFAULT 'candidate',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER,
    file_number INTEGER UNIQUE,
    title TEXT NOT NULL,
    hook_text TEXT,
    hook_type TEXT,
    script TEXT,
    video_path TEXT,
    duration_sec REAL,
    youtube_video_id TEXT,
    upload_status TEXT DEFAULT 'PENDING',
    scheduled_publish_at TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS provenance_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER,
    filename TEXT NOT NULL,
    source_url TEXT,
    author TEXT,
    license_type TEXT,
    commercial_use BOOLEAN DEFAULT 1,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER,
    youtube_video_id TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shown_in_feed INTEGER DEFAULT 0,
    viewed_vs_swiped_pct REAL DEFAULT 0.0,
    avg_percentage_viewed REAL DEFAULT 0.0,
    avg_view_duration_sec REAL DEFAULT 0.0,
    subscribers_gained INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS dynamic_weights (
    weight_key TEXT PRIMARY KEY,
    weight_value REAL DEFAULT 1.0,
    sample_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS content_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_number INTEGER UNIQUE,
    title TEXT NOT NULL,
    main_key_point TEXT,
    story_summary TEXT,
    content_pillar TEXT,
    duration_sec REAL,
    youtube_video_id TEXT,
    status TEXT DEFAULT 'rendered',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);
```

---

## 5. REPOSITORY STRUCTURE (CANONICAL)

```
c:\YT-SHORTS\
├── analytics/                 # YouTube Analytics API sync & heuristic weight optimization
│   ├── decision_engine.py     # Bounded adaptive performance weighting
│   ├── metrics.py             # Performance metric normalization
│   └── sync.py                # YouTube Analytics API v2 client
├── assets/                    # Static audio beds, sub-bass assets, and fonts
├── content/                   # Investigative research, scripting, and scene direction
│   ├── claim_verifier.py      # Wikipedia source text extraction & claim verification gate
│   ├── hooks.py               # Dynamic hook generation & weighted selection
│   ├── scene_planner.py       # Claim-local visual intent director & storyboard engine
│   ├── seo.py                 # Structured metadata & documentary descriptions
│   └── story_brain.py         # 36-second retention-focused script synthesis
├── core/                      # Production infrastructure & foundation
│   ├── config.py              # Strongly-typed configuration dataclasses
│   ├── database.py            # SQLite database layer with WAL mode & timeouts
│   ├── llm_router.py          # Resilient multi-cloud LLM gateway
│   ├── logging.py             # Unified timestamped logger
│   ├── manifest.py            # Immutable JSON render manifest builder
│   ├── scheduler.py           # US timezone production clock & publishing windows
│   └── state_store.py         # Crash-safe SQLite state synchronization
├── media/                     # Broadcast video & audio rendering engine
│   ├── audio_bed.py           # EBU R128 audio mastering, ambient drone & ducking
│   ├── captions.py            # Word-synced ASS kinetic caption generator
│   ├── compositor.py          # Stream-copy concatenation & editorial motion compositor
│   ├── explanatory_graphic.py # Fact-grounded procedural technical schematics
│   ├── images.py              # Wikimedia Commons/Pexels harvester & dedup waterfall
│   └── voice.py               # Edge-TTS neural voice synthesis with boundary sync
├── publisher/                 # YouTube publication client
│   └── youtube.py             # Headless chunked resumable uploader
├── qc/                        # 3-Layer Quality Control & verification
│   ├── contact_sheet.py       # Rendered clip contact sheet generator
│   └── frame_verifier.py      # L1 existence, L2 match, L3 timeline sampling, black/freeze QC
├── tests/                     # Continuous integration production verification
│   ├── _guard.py              # Database isolation sandbox guard
│   ├── test_audit.py          # Zero-hardcoding and configuration security audit
│   ├── test_novelty_regression.py # 3-Level topic novelty and non-repetition tests
│   ├── test_preflight.py      # Pre-run environment & credentials validation
│   └── test_regression.py     # Full FFmpeg compositor & visual QC golden test
├── .github/workflows/         # Cloud automation workflows
│   └── daily_nexus.yml        # Scheduled production & review run workflow
├── main.py                    # Master production orchestrator
├── PRD.md                     # Single authoritative specification
├── README.md                  # Operational guide & system overview
└── requirements.txt           # Verified pinned runtime dependencies
```

---

## 6. OPERATIONAL CLI FLAGS

| Flag | Behavior |
|---|---|
| *(no flags)* | Full autonomous production run. Uploads to YouTube if `APP_MODE=production`. |
| `--dry-run` | Executes the complete pipeline through media rendering, visual QC, and contact sheet generation, but **skips all database commits and YouTube network calls**. |
| `--skip-upload` | Executes full rendering and records the video in SQLite, but skips uploading to YouTube. |
| `--force-topic "Name"` | Bypasses automated Wikipedia candidate discovery and forces a specific topic name. |

---

*NEXUS VAULTS 2.0 Authoritative PRD · Consolidated Single Source of Truth · Confirmed September 20, 2026*
