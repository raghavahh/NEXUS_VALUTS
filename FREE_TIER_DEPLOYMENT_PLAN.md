# AI Video Factory — Free-Tier GitHub Actions Deployment Plan (A→Z)

**Goal:** Run the autonomous documentary Shorts engine 100% free on GitHub Actions (manual trigger only), with **dynamic topic discovery → scoring → top-1 selection → full render → QC → optional publish**. Zero hardcoding, zero predefined video lists, zero recurring cost.

---

## 1. ARCHITECTURE OVERVIEW (WHAT RUNS WHERE)

| Component | Runs On | Cost | Trigger |
|-----------|---------|------|---------|
| Topic Discovery + Scoring | GitHub Actions `windows-latest` | $0 (free mins) | Manual `workflow_dispatch` |
| Research / Claim Verification | Same runner (cloud LLMs via free tiers) | $0 | Inline |
| Asset Harvest (Wikimedia/Wikipedia) | Same runner (public APIs) | $0 | Inline |
| Voice Synthesis (Edge-TTS) | Same runner (local, free) | $0 | Inline |
| Compositor (FFmpeg) | Same runner (pre-installed) | $0 | Inline |
| 3-Layer QC | Same runner | $0 | Inline |
| YouTube Upload (resumable) | Same runner (OAuth) | $0 quota | Only if `AI_VIDEO_FACTORY_LIVE=true` |
| State Persistence | GitHub Artifacts + `factory-state` branch | $0 | Auto |

**Single workflow file:** `.github/workflows/daily_aivf.yml` (already exists, manual-only)

---

## 2. DYNAMIC TOPIC DISCOVERY & SCORING PIPELINE (NO HARDCODING)

### 2.1 Source: Wikipedia Category Traversal (Live)
- **Entry points** (configurable via `RESEARCH_CONTENT_PILLARS`):
  - `Classified History` → Category:Declassified_documents, Category:Clandestine_operations, Category:Covert_operations
  - `Unexplained Events` → Category:Unexplained_disappearances, Category:Anomalous_phenomena, Category:Maritime_mysteries
  - `Scientific Mysteries` → Category:Physics_paradoxes, Category:Unsolved_problems_in_physics, Category:Cosmology_mysteries
  - `Strange Real Events` → Category:Historical_anomalies, Category:Lost_expeditions, Category:Anomalous_artifacts

### 2.2 Discovery Flow (in `research/discover.py`)
```
1. For each pillar category → fetch 50 page titles via Wikipedia API (generator=categorymembers)
2. Filter: must have ≥3 sections, ≥2000 chars, ≥1 image, not a disambiguation/list/redirect
3. For each candidate → fetch summary + first 3 sections (source text for claim verification)
4. Score each candidate on 5 dimensions (0-100 each):
   a) Narrative Density      — distinct claimable facts per 1000 chars
   b) Visual Evidence Richness — count of Wikimedia/Wikipedia images matching primary entities
   c) Hook Potential         — contradiction/impossible-detail/hidden-evidence/countdown/location signals
   d) Novelty vs History     — 3-level check: exact dup, same-angle (>60% summary overlap), same-subject-new-angle (allowed)
   e) Pillar Weight          — dynamic weight from `dynamic_weights` table (learned from analytics)
5. Composite Score = Σ(weight_i × dimension_i)
   Weights: Narrative 0.25, Visual 0.25, Hook 0.20, Novelty 0.20, Pillar 0.10
6. Return top N (config: RESEARCH_MAX_CANDIDATES=3) to Growth Brain
```

### 2.3 Growth Brain (in `research/growth_brain.py`)
- Takes top 3 candidates
- Uses LLM (routed: NVIDIA→Groq→Gemini→OpenRouter) to:
  - Extract 3-4 verified facts + 1 unsolved conflict per candidate
  - Propose 5 hook angles per candidate (scored against dynamic hook weights)
  - Select best candidate + best hook + narrative angle
- Output: `{topic, cluster, facts[], conflict, hook, hook_type, media_preflight}`

### 2.4 Media Preflight (in `research/media_preflight.py`)
- For selected topic, query Wikimedia Commons + Wikipedia article images
- Count relevant authentic assets (relevance ≥0.60)
- Estimate survivors after 5-tier dedup
- **Gate:** Must have ≥4 authentic assets estimated → `ELIGIBLE`/`STRONG`, else `REJECTED` → pipeline defers

### 2.5 Final Selection
- **Only 1 topic proceeds** per run (the top-scoring approved candidate)
- All other candidates discarded (but logged for audit)
- Topic recorded in SQLite with `status='selected'` (atomic)

---

## 3. CONTENT CREATION AT RUNTIME (ZERO PREDEFINED)

| Stage | Input | Output | Dynamic? |
|-------|-------|--------|----------|
| Claim Verification | Wikipedia source text | Verified fact sentences | ✅ Live fetch |
| Hook Generation | Facts + conflict + source text | 5 scored hooks | ✅ LLM |
| Script Writing | Selected hook + facts + conflict | 68-84 word narration | ✅ LLM |
| Claim Verification Gate | Script sentences vs source text | Pass/Regenerate/Defer | ✅ Automated |
| Scene Planning | Verified script + voice duration | 10-15 scenes with visual contracts | ✅ LLM |
| Asset Harvest | Scene contracts | 10-15 unique authenticated assets | ✅ Live API |
| Explanatory Graphics | Gaps where authentic <4 | ≤3 truthful schematics | ✅ Generated |
| Voice Synthesis | Final narration | Edge-TTS MP3 + word timings | ✅ Local |
| Audio Mastering | Voice + ambient drone | -14 LUFS mastered AAC | ✅ FFmpeg |
| Compositor | Manifest + audio + ASS | 1080×1920 MP4 | ✅ FFmpeg |
| QC | Rendered video + manifest | Pass/Fail + contact sheet | ✅ Automated |

**Nothing is pre-written.** Every run: new topic → new research → new script → new assets → new video.

---

## 4. QUALITY CONTROL GATES (100% PASS REQUIRED)

| Gate | Check | Threshold | Fail Action |
|------|-------|-----------|-------------|
| **Duration** | `ffprobe` final MP4 | 29.5s – 40.5s | Defer run |
| **Audio Loudness** | `ffmpeg loudnorm` measured LUFS | -14.0 ±1.0 LUFS | Defer run |
| **Visual L1** | All scene clips exist, non-empty | 100% | Defer run |
| **Visual L2** | Rendered clip dHash vs source ≥0.40 | 100% scenes | Defer run |
| **Visual L3** | Composite frame samples match scene clips Hamming ≤20 | 100% scenes | Defer run |
| **Black Frames** | >0.2s black | 0 | Defer run |
| **Freeze Frames** | >1.5s frozen | 0 | Defer run |
| **Asset Budget** | Authentic ≥4, Generated ≤3 | Hard | Defer run |
| **Dedup** | 0 duplicate URLs / SHAs / dHash near-dups | 0 | Defer run |
| **Novelty** | 3-level check passed | APPROVED | Defer run |

**Contact Sheet** generated on every run (artifact) — visual audit trail.

---

## 5. GITHUB ACTIONS WORKFLOW DESIGN (EXISTING + ENHANCEMENTS)

### 5.1 Current Workflow (`.github/workflows/daily_aivf.yml`) — Already Correct
- Manual `workflow_dispatch` with optional `force_topic`
- `windows-latest` runner (FFmpeg + Windows fonts)
- Checkout + `factory-state` branch restore
- Python 3.12 + pip cache + FFmpeg install (Chocolatey)
- Run modes:
  - `AI_VIDEO_FACTORY_LIVE=true` → `python main.py` (uploads)
  - `AI_VIDEO_FACTORY_LIVE=false` → `python main.py --skip-upload` (review)
- Artifacts: rendered video (7 days), DB state (14 days)
- Live mode: push `channel.db` + `channel_brain.json` to `factory-state` branch

### 5.2 Required Enhancements (Free-Tier Optimizations)

```yaml
# Add to workflow env:
CHOCOLATEY_CACHE_KEY: "choco-{{ runner.os }}-{{ hashFiles('**/requirements.txt') }}"

# Add caching step BEFORE "Install dependencies & FFmpeg":
- name: Cache Chocolatey
  id: choco-cache
  uses: actions/cache@v4
  with:
    path: C:\ProgramData\chocolatey
    key: ${{ env.CHOCOLATEY_CACHE_KEY }}
    restore-keys: |
      choco-${{ runner.os }}-

- name: Install FFmpeg (cached)
  if: steps.choco-cache.outputs.cache-hit != 'true'
  run: choco install ffmpeg -y --no-progress

# Add: Pre-flight validation step (fail fast before long run)
- name: Preflight Validation
  run: python tests/test_preflight.py

# Add: Hardcoding audit (ensure zero secrets in code)
- name: Hardcoding Audit
  run: python tests/test_audit.py
```

### 5.3 Workflow Inputs (Extend)
```yaml
on:
  workflow_dispatch:
    inputs:
      force_topic:
        description: "Optional forced topic name"
        type: string
        default: ""
        required: false
      dry_run:
        description: "Full render + QC, no DB commits, no upload"
        type: boolean
        default: false
        required: false
      skip_qc:
        description: "Skip 3-layer visual QC (faster, DANGEROUS)"
        type: boolean
        default: false
        required: false
```

### 5.4 Pass Inputs to CLI
```yaml
$dryRun = '${{ inputs.dry_run }}' -eq 'true'
$skipQc = '${{ inputs.skip_qc }}' -eq 'true'
$topicArgs = @()
if ($forcedTopic) { $topicArgs += @("--force-topic", $forcedTopic) }
if ($dryRun) { $topicArgs += "--dry-run" }
if ($skipQc) { $topicArgs += "--skip-qc" }  # add flag to main.py
python main.py @topicArgs
```

---

## 6. SECRETS & VARIABLES CONFIGURATION (ONE-TIME)

### 6.1 Repository Secrets (Settings → Secrets and variables → Actions → Secrets)

| Secret Name | Source | Free Tier Limits |
|-------------|--------|------------------|
| `NVIDIA_API_KEY` | https://build.nvidia.com/ | 1000 req/day free |
| `GROQ_API_KEY` | https://console.groq.com/keys | 14,400 req/day free |
| `GEMINI_API_KEY` | https://aistudio.google.com/ | 1,500 req/day free |
| `OPENROUTER_API_KEY` | https://openrouter.ai/settings/keys | Free models unlimited |
| `YT_CLIENT_ID` | GCP OAuth Desktop Client | Unlimited |
| `YT_CLIENT_SECRET` | GCP OAuth Desktop Client | Unlimited |
| `YT_REFRESH_TOKEN` | Local auth flow (see below) | Expires if unused 7+ days |
| `PEXELS_API_KEY` | https://www.pexels.com/api/ | 200 req/hour free |

### 6.2 Repository Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `AI_VIDEO_FACTORY_LIVE` | `false` | Start in review mode |
| `CHANNEL_NICHE` | `history` | Analytics pillar weighting |
| `CHANNEL_NAME` | `NEXUS VAULTS` | Video header badge |
| `CHANNEL_HANDLE` | `NEXUS_VAULTS` | Video header badge |

### 6.3 YouTube OAuth Refresh Token Generation (One-Time Local)

```bash
# Run ONCE on your machine (not in Actions):
cd NEXUS_VALUTS
python tools/get_yt_refresh_token.py  # create this helper script
# Output: YT_REFRESH_TOKEN=1//0xxxxx...
# Paste into GitHub Secrets
```

**Helper script (`tools/get_yt_refresh_token.py`):**
```python
#!/usr/bin/env python3
import urllib.parse, urllib.request, json, http.server, socketserver, webbrowser, threading, time, sys, os

client_id = os.getenv("YT_CLIENT_ID") or input("YT_CLIENT_ID: ").strip()
client_secret = os.getenv("YT_CLIENT_SECRET") or input("YT_CLIENT_SECRET: ").strip()
port = 8080
redirect = f"http://localhost:{port}/"
scope = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/yt-analytics.readonly"
auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={urllib.parse.quote(redirect)}&response_type=code&scope={urllib.parse.quote(scope)}&access_type=offline&prompt=consent"

print(f"\n1. Open this URL in browser:\n{auth_url}\n")
code_holder = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/?code="):
            code_holder["code"] = self.path.split("code=")[1].split("&")[0]
            self.send_response(200); self.end_headers(); self.wfile.write(b"Success! Close this tab.")
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass

with socketserver.TCPServer(("", port), Handler) as srv:
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    webbrowser.open(auth_url)
    while "code" not in code_holder:
        time.sleep(0.5)
    srv.shutdown()

code = code_holder["code"]
data = urllib.parse.urlencode({
    "code": code, "client_id": client_id, "client_secret": client_secret,
    "redirect_uri": redirect, "grant_type": "authorization_code"
}).encode()
resp = json.loads(urllib.request.urlopen(
    urllib.request.Request("https://oauth2.googleapis.com/token", data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"})
).read())

print(f"\nYT_REFRESH_TOKEN={resp['refresh_token']}")
print("\nAdd this to GitHub Repository Secrets → YT_REFRESH_TOKEN")
```

---

## 7. LOCAL DEVELOPMENT & TESTING WORKFLOW

### 7.1 Prerequisites (Windows)
```powershell
# Install once
choco install python git ffmpeg -y
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install edge-tts Pillow yt-dlp tzdata
```

### 7.2 Local `.env` (Copy from `.env.example`, fill secrets)
```bash
cp .env.example .env
# Edit .env with your keys (NEVER commit .env)
```

### 7.3 Test Commands
```bash
# 1. Preflight (validates config, DB, FFmpeg, timezone)
python tests/test_preflight.py

# 2. Hardcoding audit (must pass with 0 findings)
python tests/test_audit.py

# 3. Novelty regression (isolated, proves dedup works)
python tests/test_novelty_regression.py

# 4. Full regression (renders 12 synthetic scenes, verifies compositor+QC)
python tests/test_regression.py

# 5. Dry-run with forced topic (full pipeline, no upload, no DB mutations)
python main.py --dry-run --force-topic "Mary Celeste"

# 6. Review mode render (full pipeline, saves to DB, skips upload)
python main.py --skip-upload --force-topic "Dyatlov Pass Incident"

# 7. Live run (uploads to YouTube) — ONLY after review approval
# Requires APP_MODE=production in .env
```

---

## 8. PROS/CONS MITIGATION TABLE (FREE TIER)

| Con | Mitigation |
|-----|------------|
| Windows runner cold start (~2-3 min) | Cache Chocolatey; accept — free tier |
| OAuth refresh token expires after 7 days inactivity | Run workflow at least weekly (manual); document in README |
| No monitoring/alerting | Check Actions tab; download artifacts; add optional webhook step if needed |
| Single video per 90-min workflow | By design — quality over quantity; manual control |
| API rate limits (free tiers) | Provider chain auto-fallback (NVIDIA→Groq→Gemini→OpenRouter); low volume (1 run = ~30 LLM calls) |
| No GPU / local inference | Not needed — Edge-TTS local, LLMs cloud-free-tier, FFmpeg CPU |
| Pexels optional but helpful | Free key takes 1 min; adds atmospheric b-roll only |
| `factory-state` branch push needs `contents: write` | Already in workflow permissions |

---

## 9. STEP-BY-STEP EXECUTION CHECKLIST

### Phase 1: Repository Setup (5 min)
- [ ] Fork repo to your GitHub account
- [ ] Clone locally: `git clone https://github.com/<you>/NEXUS_VALUTS`
- [ ] Create `tools/get_yt_refresh_token.py` from Section 6.3

### Phase 2: API Keys (10 min)
- [ ] Get NVIDIA API key → add to GitHub Secrets
- [ ] Get Groq API key → add to GitHub Secrets
- [ ] Get Gemini API key → add to GitHub Secrets
- [ ] Get OpenRouter API key → add to GitHub Secrets
- [ ] Get Pexels API key → add to GitHub Secrets
- [ ] GCP: Create project → Enable YouTube Data API v3 + YouTube Analytics API v2 → OAuth Desktop Client → add Client ID/Secret to Secrets

### Phase 3: YouTube OAuth (5 min)
- [ ] Run `python tools/get_yt_refresh_token.py` locally
- [ ] Paste `YT_REFRESH_TOKEN` to GitHub Secrets

### Phase 4: GitHub Variables (2 min)
- [ ] Add `AI_VIDEO_FACTORY_LIVE=false`
- [ ] Add `CHANNEL_NICHE=history`
- [ ] Add `CHANNEL_NAME=NEXUS VAULTS`
- [ ] Add `CHANNEL_HANDLE=NEXUS_VAULTS`

### Phase 5: Workflow Enhancements (5 min)
- [ ] Apply caching + preflight steps from Section 5.2 to `.github/workflows/daily_aivf.yml`
- [ ] Add `--skip-qc` flag support to `main.py` (optional, for faster iteration)
- [ ] Commit & push

### Phase 6: Local Validation (10 min)
- [ ] `cp .env.example .env` → fill with same keys
- [ ] `python tests/test_preflight.py` → must pass
- [ ] `python tests/test_audit.py` → must pass (0 findings)
- [ ] `python main.py --dry-run --force-topic "Mary Celeste"` → produces MP4 in OUTPUT/

### Phase 7: First GitHub Actions Run (Review Mode)
- [ ] Go to Actions → AI Video Factory Manual Run → Run workflow
- [ ] Leave `force_topic` empty (tests dynamic discovery)
- [ ] `dry_run=false`, `skip_qc=false`
- [ ] Watch run (≈8-12 min)
- [ ] Download `aivf-rendered-short` artifact → verify MP4 + contact sheet
- [ ] Download `aivf-database-state` artifact → verify `channel.db` has 1 topic + 1 video

### Phase 8: Iterate & Approve
- [ ] Run 2-3 more times with different forced topics to verify variety
- [ ] Check contact sheets for visual quality
- [ ] Verify no duplicate topics/assets across runs

### Phase 9: Go Live
- [ ] Set `AI_VIDEO_FACTORY_LIVE=true` (Repository Variables)
- [ ] Run workflow → publishes to YouTube (scheduled next day 19:00 ET)
- [ ] Verify in YouTube Studio → Short appears as "Scheduled"

### Phase 10: Ongoing Operation
- [ ] Run manually whenever you want a new Short
- [ ] Keep `AI_VIDEO_FACTORY_LIVE=true` for auto-publish, or `false` for review-first
- [ ] Run at least once/week to keep OAuth token fresh
- [ ] Monitor Actions → Artifacts for rendered videos & DB backups

---

## 10. DYNAMIC TOPIC SCORING DETAILS (FOR REFERENCE)

**Scoring Formula (in `research/growth_brain.py`):**

```
composite_score = 
  0.25 * narrative_density_score      # facts per 1000 chars, normalized 0-100
+ 0.25 * visual_richness_score        # relevant Wikimedia/Wiki images count, normalized
+ 0.20 * hook_potential_score         # LLM-scored hook angles vs dynamic hook weights
+ 0.20 * novelty_score                # 100 if APPROVED, 0 if REJECTED (gate)
+ 0.10 * pillar_weight                # from dynamic_weights table (learned)
```

**Hook Scoring (in `content/hooks.py`):**
- 5 hook categories: CONTRADICTION, IMPOSSIBLE DETAIL, HIDDEN EVIDENCE, COUNTDOWN, LOCATION
- Each hook variant scored against `dynamic_weights["hook:<category>"]`
- Minimum threshold: `HOOK_MIN_SCORE=0.75` (configurable)

**Novelty Gate (in `core/database.py::verify_topic_novelty`):**
- Level 1: Exact normalized title match → REJECT
- Level 2: >60% summary token overlap + >40% title token overlap → REJECT (same angle)
- Level 3: Title overlap but <55% summary overlap → ALLOW (new evidence on same subject)

---

## 11. FILES TO CREATE/MODIFY (SUMMARY)

| File | Action | Purpose |
|------|--------|---------|
| `.github/workflows/daily_aivf.yml` | Patch (add caching, preflight, audit, skip-qc input) | Free-tier optimization + safety gates |
| `tools/get_yt_refresh_token.py` | Create | One-time OAuth helper |
| `main.py` | Patch (add `--skip-qc` flag) | Faster iteration option |
| `README.md` | Update | Document free-tier setup, weekly run requirement |
| `.env` (local only) | Create from `.env.example` | Local development config |
| GitHub Secrets | Configure (8 secrets) | Runtime credentials |
| GitHub Variables | Configure (4 variables) | Runtime switches |

---

## 12. SUCCESS CRITERIA (DEFINITION OF DONE)

1. ✅ `python tests/test_preflight.py` passes locally & in Actions
2. ✅ `python tests/test_audit.py` passes (0 hardcoded findings)
3. ✅ `python main.py --dry-run --force-topic "X"` produces valid MP4 + contact sheet
4. ✅ GitHub Actions review run completes <15 min, uploads artifacts
5. ✅ Artifact MP4 plays, 30-40s, 1080×1920, kinetic subtitles, -14 LUFS audio
6. ✅ Contact sheet shows 10-15 scenes, ≥4 authentic assets, 0 duplicates
7. ✅ `AI_VIDEO_FACTORY_LIVE=true` run publishes to YouTube (scheduled)
8. ✅ `factory-state` branch updated with new `channel.db` + `channel_brain.json`
9. ✅ Second run discovers NEW topic (novelty gate works), no repeats
10. ✅ Total monthly cost: $0 (GitHub Actions free tier + API free tiers)

---

## 13. ROLLBACK / DISASTER RECOVERY

| Scenario | Recovery |
|----------|----------|
| Workflow fails mid-upload | `UPLOAD_ATTEMPTED` guard blocks re-upload; check YouTube Studio manually |
| `factory-state` branch corrupted | Download `aivf-database-state` artifact → restore locally → force-push |
| OAuth token expired | Re-run `tools/get_yt_refresh_token.py` → update Secret |
| API key quota exhausted | Chain falls back automatically; add more keys if needed |
| Bad video published | Delete in YouTube Studio; DB retains record; next run continues |

---

**This plan is complete.** Every component exists in the codebase. The only work is: **configure secrets → enhance workflow caching → run once locally → run once in Actions review → go live.**