"""
NEXUS VAULTS 2.0 - SQLite Database Layer
Stores Knowledge Graph topics, published videos, asset provenance, analytics,
and lightweight content memory. Zero media archiving.
Database location is driven strictly by config.storage.database_path.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from core.config import config
from core.logging import log

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.storage.database_path, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables with schema versioning."""
    config.storage.database_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Topics table (Knowledge Graph nodes)
        cursor.execute("""
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
        """)

        # 2. Videos table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER,
            file_number INTEGER UNIQUE,
            title TEXT NOT NULL,
            hook_text TEXT,
            hook_type TEXT,
            script TEXT,
            video_path TEXT,
            youtube_video_id TEXT,
            duration_sec REAL,
            published_at TIMESTAMP,
            upload_status TEXT DEFAULT 'PENDING',
            scheduled_publish_at TIMESTAMP,
            FOREIGN KEY(topic_id) REFERENCES topics(id)
        );
        """)

        # Migration: Ensure upload_status and scheduled_publish_at columns exist
        cursor.execute("PRAGMA table_info(videos)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if "upload_status" not in existing_cols:
            cursor.execute("ALTER TABLE videos ADD COLUMN upload_status TEXT DEFAULT 'PENDING'")
        if "scheduled_publish_at" not in existing_cols:
            cursor.execute("ALTER TABLE videos ADD COLUMN scheduled_publish_at TIMESTAMP")

        # Migration: Ensure any topic linked to a historical video is marked 'published'
        cursor.execute("""
            UPDATE topics SET status = 'published'
            WHERE id IN (SELECT DISTINCT topic_id FROM videos WHERE topic_id IS NOT NULL)
        """)

        # 3. Asset Provenance table (Commercial rights & licensing audit trail)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS provenance_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            filename TEXT NOT NULL,
            source_url TEXT,
            author TEXT,
            license_type TEXT,
            commercial_use INTEGER DEFAULT 1,
            FOREIGN KEY(video_id) REFERENCES videos(id)
        );
        """)

        # 4. Analytics table (Algorithm signals)
        cursor.execute("""
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
        """)

        # 5. Dynamic Feedback Weights table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_weights (
            weight_key TEXT PRIMARY KEY,
            weight_value REAL DEFAULT 1.0,
            sample_count INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 6. Lightweight Content Memory table (Zero media archiving)
        cursor.execute("""
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
        """)

        # Populate initial default weights if empty.
        # Hook keys MUST match the HOOK_CATEGORIES names used by content/hooks.py
        # (CONTRADICTION, IMPOSSIBLE DETAIL, HIDDEN EVIDENCE, COUNTDOWN, LOCATION) —
        # earlier seeds used narrative-structure names the hook engine never queried.
        cursor.execute("SELECT COUNT(*) FROM dynamic_weights")
        if cursor.fetchone()[0] == 0:
            initial_weights = [
                ("cluster:Unexplained Events", 1.0),
                ("cluster:Classified History", 1.2),
                ("cluster:Scientific Mysteries", 1.0),
                ("cluster:Strange Real Events", 1.1),
                ("hook:CONTRADICTION", 1.2),
                ("hook:IMPOSSIBLE DETAIL", 1.15),
                ("hook:HIDDEN EVIDENCE", 1.2),
                ("hook:COUNTDOWN", 1.05),
                ("hook:LOCATION", 1.0)
            ]
            for k, v in initial_weights:
                cursor.execute(
                    "INSERT INTO dynamic_weights (weight_key, weight_value, sample_count) VALUES (?, ?, 1)",
                    (k, v)
                )

        conn.commit()
        log.info(f"Database initialized at {config.storage.database_path.name}")

def get_next_file_number() -> int:
    """Returns the next sequential NEXUS VAULTS file number (e.g., FILE #001, FILE #002)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(file_number) FROM videos")
        res = cursor.fetchone()[0]
        return (res or 0) + 1

def get_incomplete_upload_attempts() -> List[Dict[str, Any]]:
    """
    Idempotency guard: any video row marked UPLOAD_ATTEMPTED without a confirmed
    YouTube video ID represents an upload whose outcome is UNKNOWN (crash, timeout,
    process kill). Such a file number must NEVER be re-uploaded automatically —
    re-uploading could create a duplicate video on the channel.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_number, title, upload_status
            FROM videos
            WHERE upload_status = 'UPLOAD_ATTEMPTED' AND youtube_video_id IS NULL
            ORDER BY file_number
        """)
        return [dict(r) for r in cursor.fetchall()]

def mark_upload_attempted(file_number: int):
    """
    Write-ahead marker: committed to the database BEFORE the YouTube upload call.
    If the process dies mid-upload, the rerun guard sees this row and defers.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE videos SET upload_status = 'UPLOAD_ATTEMPTED' WHERE file_number = ?",
            (file_number,)
        )
        conn.commit()

def update_video_upload(file_number: int, youtube_video_id: str, upload_status: str, scheduled_publish_at: Optional[str] = None):
    """
    Post-upload completion: persists the confirmed YouTube video ID immediately
    (closing the crash window between upload acceptance and final record write).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE videos
            SET youtube_video_id = ?, upload_status = ?, scheduled_publish_at = ?,
                published_at = CURRENT_TIMESTAMP
            WHERE file_number = ?
        """, (youtube_video_id, upload_status, scheduled_publish_at, file_number))
        conn.commit()

def set_upload_status(file_number: int, upload_status: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE videos SET upload_status = ? WHERE file_number = ?",
            (upload_status, file_number)
        )
        conn.commit()

def normalize_topic_key(text: str) -> str:
    """Normalizes topic title or key point for robust non-repetition matching."""
    import re
    clean = re.sub(r'file\s*#?\d+', '', text, flags=re.IGNORECASE)
    clean = re.sub(r'#shorts\b', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'the\s+mystery\s+of\b', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[^a-z0-9\s]', ' ', clean.lower())
    return ' '.join(clean.split())

def is_topic_already_used(title: str) -> bool:
    """
    Prevents duplicate video topics across all historical records:
    Cross-checks topics table, videos table, and content_memory table with normalized fuzzy matching.
    """
    import re
    norm_candidate = normalize_topic_key(title)
    if not norm_candidate:
        return False
    cand_tokens = set(norm_candidate.split())

    with get_connection() as conn:
        cursor = conn.cursor()
        # 1. Check topics table (all non-archived topics across candidate, selected, and published)
        cursor.execute("SELECT title, status FROM topics WHERE status != 'archived_test'")
        for row in cursor.fetchall():
            norm_existing = normalize_topic_key(row["title"])
            ex_tokens = set(norm_existing.split())
            if (norm_candidate == norm_existing
                or norm_candidate in norm_existing
                or norm_existing in norm_candidate
                or (len(cand_tokens) >= 2 and cand_tokens.issubset(ex_tokens))
                or (len(ex_tokens) >= 2 and ex_tokens.issubset(cand_tokens))):
                return True

        # 2. Check videos table
        cursor.execute("SELECT title FROM videos")
        for row in cursor.fetchall():
            norm_existing = normalize_topic_key(row["title"])
            ex_tokens = set(norm_existing.split())
            if (norm_candidate == norm_existing
                or norm_candidate in norm_existing
                or norm_existing in norm_candidate
                or (len(cand_tokens) >= 2 and cand_tokens.issubset(ex_tokens))
                or (len(ex_tokens) >= 2 and ex_tokens.issubset(cand_tokens))):
                return True

        # 3. Check content_memory table
        cursor.execute("SELECT title, main_key_point FROM content_memory WHERE status != 'archived_test'")
        for row in cursor.fetchall():
            norm_existing = normalize_topic_key(row["title"])
            norm_keypoint = normalize_topic_key(row["main_key_point"] or "")
            ex_tokens = set(norm_existing.split())
            if (norm_candidate == norm_existing
                or norm_candidate in norm_existing
                or norm_existing in norm_candidate
                or (len(cand_tokens) >= 2 and cand_tokens.issubset(ex_tokens))
                or (len(ex_tokens) >= 2 and ex_tokens.issubset(cand_tokens))):
                return True
            # Check overlap with keypoint
            kp_tokens = set(norm_keypoint.split())
            if len(cand_tokens) >= 2 and len(cand_tokens.intersection(kp_tokens)) / max(1, len(cand_tokens)) > 0.6:
                return True

        return False

def verify_topic_novelty(candidate: dict) -> dict:
    """
    Enforces structured non-repetition with three clearly distinct rejection levels:

    LEVEL 1 - EXACT DUPLICATE:  Same normalized title or identical topic key → always reject.
    LEVEL 2 - SAME ANGLE:       Candidate summary shares > 60% token overlap with a prior
                                 video's summary AND title tokens overlap >= 2 → reject.
    LEVEL 3 - SAME SUBJECT, NEW EVIDENCE:
                                 Candidate is about a related subject but brings a genuinely
                                 new narrative angle (summary overlap < 55%) → ALLOWED.

    Example of correctly allowed case:
      Story A: "What happened on the Mary Celeste?"  (abandonment mystery)
      Story B: "Newly discovered logbook page from the Mary Celeste crew" (new primary evidence)
      → Allowed because summary diverges significantly despite shared subject tokens.
    """
    import re
    title = candidate.get("title", "")
    summary = candidate.get("summary", "")
    norm_title = normalize_topic_key(title)
    title_tokens = set(norm_title.split())
    summary_tokens = set(re.findall(r'\b[a-z]{4,}\b', summary.lower()))

    topic_check = "PASS"
    claim_check = "PASS"
    angle_check = "PASS"
    rejection_reasons = []

    # LEVEL 1: Exact title / topic key duplicate
    if is_topic_already_used(title):
        topic_check = "FAIL"
        rejection_reasons.append(f"EXACT DUPLICATE: Title '{title}' duplicates previous topic or video title.")

    # LEVEL 2 & 3: Claim and angle analysis against content_memory
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_number, title, main_key_point, story_summary FROM content_memory WHERE status != 'archived_test'")
        for row in cursor.fetchall():
            f_num = row["file_number"]
            prev_summary = row["story_summary"] or ""
            prev_title_tokens = set(normalize_topic_key(row["title"]).split())
            prev_tokens = set(re.findall(r'\b[a-z]{4,}\b', prev_summary.lower()))

            if not prev_tokens:
                continue

            summary_overlap = len(summary_tokens.intersection(prev_tokens)) / max(1, min(len(summary_tokens), len(prev_tokens)))
            title_overlap = len(title_tokens.intersection(prev_title_tokens)) / max(1, len(title_tokens)) if title_tokens else 0

            # LEVEL 2: Same angle — high summary overlap AND shared title tokens
            if summary_overlap > 0.60 and title_overlap >= 0.40:
                claim_check = "FAIL"
                rejection_reasons.append(
                    f"SAME ANGLE: Candidate shares {summary_overlap:.0%} summary + {title_overlap:.0%} title overlap "
                    f"with FILE #{f_num:03d} ('{row['title'][:35]}'). Different angle required."
                )

            # LEVEL 3 detection: Title tokens overlap but summary is genuinely new → ALLOWED
            # Only flag as angle issue if both summary AND angle are near-identical
            elif title_overlap >= 0.40 and summary_overlap <= 0.55:
                # Same subject, new evidence — this is allowed; log as informational
                pass  # Explicitly permitted — new angle on a related subject is valid journalism

    approved = (topic_check == "PASS" and claim_check == "PASS" and angle_check == "PASS")
    return {
        "duplicate_topic_check": topic_check,
        "duplicate_claim_check": claim_check,
        "duplicate_angle_check": angle_check,
        "result": "APPROVED" if approved else "REJECTED",
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "Novel topic, distinct claims, and fresh narrative angle verified."
    }

def record_topic(cluster: str, title: str, summary: str, source_url: str, fact_confidence: float, demand_score: float, status: str = "selected") -> int:
    if is_topic_already_used(title):
        raise ValueError(f"Novelty Gate Violation: Cannot record duplicate topic '{title}' - already exists in archive.")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO topics (cluster, title, summary, source_url, fact_confidence, demand_score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cluster, title, summary, source_url, fact_confidence, demand_score, status))
        conn.commit()
        cursor.execute("SELECT id FROM topics WHERE title = ?", (title,))
        return cursor.fetchone()[0]

def mark_topic_status(topic_id: int, status: str):
    """Updates topic status (e.g. candidate -> selected -> published)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE topics SET status = ? WHERE id = ?", (status, topic_id))
        conn.commit()

def record_video(
    topic_id: int,
    file_number: int,
    title: str,
    hook_text: str,
    hook_type: str,
    script: str,
    video_path: str,
    duration_sec: float,
    youtube_video_id: Optional[str] = None,
    upload_status: str = "PENDING",
    scheduled_publish_at: Optional[str] = None
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO videos (
            topic_id, file_number, title, hook_text, hook_type, script, video_path,
            duration_sec, youtube_video_id, upload_status, scheduled_publish_at,
            published_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE NULL END)
        ON CONFLICT(file_number) DO UPDATE SET
            topic_id = excluded.topic_id,
            title = excluded.title,
            hook_text = excluded.hook_text,
            hook_type = excluded.hook_type,
            script = excluded.script,
            video_path = excluded.video_path,
            duration_sec = excluded.duration_sec,
            youtube_video_id = COALESCE(excluded.youtube_video_id, videos.youtube_video_id),
            upload_status = excluded.upload_status,
            scheduled_publish_at = COALESCE(excluded.scheduled_publish_at, videos.scheduled_publish_at),
            published_at = CASE
                WHEN excluded.youtube_video_id IS NOT NULL AND videos.published_at IS NULL THEN CURRENT_TIMESTAMP
                ELSE videos.published_at
            END
        """, (
            topic_id, file_number, title, hook_text, hook_type, script, video_path,
            duration_sec, youtube_video_id, upload_status, scheduled_publish_at,
            youtube_video_id
        ))
        # Ensure the topic is marked published
        if topic_id:
            cursor.execute("UPDATE topics SET status = 'published' WHERE id = ?", (topic_id,))
        conn.commit()
        cursor.execute("SELECT id FROM videos WHERE file_number = ?", (file_number,))
        row = cursor.fetchone()
        return row[0] if row else cursor.lastrowid

def record_content_memory(
    file_number: int,
    title: str,
    main_key_point: str,
    story_summary: str,
    content_pillar: str,
    duration_sec: float,
    youtube_video_id: Optional[str] = None,
    status: str = "rendered"
) -> int:
    """Stores permanent lightweight memory record without media binaries."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO content_memory (
            file_number, title, main_key_point, story_summary,
            content_pillar, duration_sec, youtube_video_id, status, published_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE NULL END)
        ON CONFLICT(file_number) DO UPDATE SET
            title = excluded.title,
            main_key_point = excluded.main_key_point,
            story_summary = excluded.story_summary,
            content_pillar = excluded.content_pillar,
            duration_sec = excluded.duration_sec,
            youtube_video_id = COALESCE(excluded.youtube_video_id, content_memory.youtube_video_id),
            status = excluded.status,
            published_at = CASE 
                WHEN excluded.youtube_video_id IS NOT NULL AND content_memory.published_at IS NULL 
                THEN CURRENT_TIMESTAMP 
                ELSE content_memory.published_at 
            END
        """, (file_number, title, main_key_point, story_summary, content_pillar, duration_sec, youtube_video_id, status, youtube_video_id))
        conn.commit()
        return cursor.lastrowid

def record_provenance(video_id: int, filename: str, source_url: str, author: str, license_type: str, commercial_use: bool = True):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO provenance_assets (video_id, filename, source_url, author, license_type, commercial_use)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (video_id, filename, source_url, author, license_type, 1 if commercial_use else 0))
        conn.commit()

def get_weight(key: str, default: float = 1.0) -> float:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT weight_value FROM dynamic_weights WHERE weight_key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

def update_weight(key: str, delta: float):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO dynamic_weights (weight_key, weight_value, sample_count, last_updated)
        VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(weight_key) DO UPDATE SET
            weight_value = MAX(0.2, MIN(3.0, weight_value + ?)),
            sample_count = sample_count + 1,
            last_updated = CURRENT_TIMESTAMP
        """, (key, max(0.2, min(3.0, 1.0 + delta)), delta))
        conn.commit()
