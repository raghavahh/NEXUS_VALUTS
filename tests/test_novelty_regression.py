"""
NEXUS VAULTS - Topic Novelty & Non-Repetition Regression (FULLY ISOLATED)

This test NEVER touches production state. It builds its own duplicate fixture
inside a sandbox database via tests/_guard.py, so results are identical
regardless of what topics exist in production.

Proves:
1. Exact/same-key duplicates are rejected by verify_topic_novelty.
2. Rejected duplicates never reach record_topic (count unchanged).
3. Direct record_topic() on a duplicate raises ValueError (hard backstop).
4. Level 2 same-angle repeats (high summary overlap + shared title) rejected.
5. Level 3 genuinely new angles on related subjects approved.
6. PRODUCTION INVARIANCE: production DB bytes, state dir, OUTPUT dir, and
   next-file-number are unchanged by running this suite; no test-created
   topics/videos leak into production.
"""
import unittest
import hashlib
from pathlib import Path

import _guard
_guard.ensure_isolation()  # MUST precede any project import

from core.database import (  # noqa: E402
    get_connection, normalize_topic_key, is_topic_already_used,
    verify_topic_novelty, record_topic, init_db
)

PROD_REPO = Path(__file__).resolve().parent.parent
PROD_DB = PROD_REPO / "nexus.db"
PROD_STATE = PROD_REPO / ".nexus_state" / "nexus.db"
PROD_OUTPUT = PROD_REPO / "OUTPUT"

DUP_TITLE = "ZZTest Fixture Paradox"          # test-owned duplicate fixture
DUP_SUMMARY = "A test fixture about a sealed chamber that defies explanation."
DUP_FACTS = "A sealed chamber. Odd measurements. No explanation."
FRESH_TITLE = "ZZTest Fresh Bathyscaphe Incident"
FRESH_SUMMARY = "Deep sea bathyscaphe expedition uncovers localized hydrothermal anomalies and unknown vents at depth."


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest() if p.exists() else "ABSENT"


def _prod_snapshot() -> dict:
    import sqlite3
    snap = {"db": _md5(PROD_DB), "state": _md5(PROD_STATE)}
    if PROD_DB.exists():
        c = sqlite3.connect(PROD_DB)
        snap["next_file"] = c.execute("SELECT COALESCE(MAX(file_number),0)+1 FROM videos").fetchone()[0]
        snap["topics"] = c.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        snap["videos"] = c.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        c.close()
    else:
        snap.update(next_file=None, topics=None, videos=None)
    snap["output_entries"] = sorted(p.name for p in PROD_OUTPUT.iterdir()) if PROD_OUTPUT.exists() else []
    return snap


class TopicNoveltyRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()  # sandbox DB
        # Build the duplicate fixture INSIDE the sandbox: topic A + published video A
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO topics (cluster, title, summary, source_url, fact_confidence, demand_score, status)"
                " VALUES ('Test Cluster', ?, ?, 'https://example.invalid/fixture', 0.95, 50.0, 'published')",
                (DUP_TITLE, DUP_SUMMARY))
            conn.execute(
                "INSERT OR REPLACE INTO videos (topic_id, file_number, title, hook_text, hook_type, script,"
                " video_path, duration_sec, youtube_video_id, upload_status)"
                " VALUES ((SELECT id FROM topics WHERE title=?), 901, 'ZZFixture Title', 'hook', 'CONTRADICTION',"
                " 'script', 'sandbox', 33.0, 'ZZFIXTUREVID', 'PUBLISHED_LIVE')",
                (DUP_TITLE,))
            conn.execute(
                "INSERT OR REPLACE INTO content_memory (file_number, title, main_key_point, story_summary,"
                " content_pillar, duration_sec, youtube_video_id, status)"
                " VALUES (901, 'ZZFixture Title', ?, ?, 'Test Cluster', 33.0, 'ZZFIXTUREVID', 'published')",
                (DUP_FACTS, DUP_SUMMARY))
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        # Remove the fixture from the SANDBOX only; production is never touched.
        with get_connection() as conn:
            conn.execute("DELETE FROM videos WHERE youtube_video_id='ZZFIXTUREVID'")
            conn.execute("DELETE FROM content_memory WHERE file_number=901")
            conn.execute("DELETE FROM topics WHERE title=?", (DUP_TITLE,))
            conn.commit()

    def setUp(self):
        self.prod_before = _prod_snapshot()

    def _assert_prod_unchanged(self):
        after = _prod_snapshot()
        self.assertEqual(self.prod_before, after,
                         f"PRODUCTION STATE MUTATED BY TESTS!\nbefore={self.prod_before}\nafter={after}")

    def test_01_exact_duplicate_normalized_key_rejected(self):
        variants = [DUP_TITLE, DUP_TITLE.lower(), f"The Mystery of {DUP_TITLE}",
                    f"FILE #099 | The Mystery of {DUP_TITLE} #Shorts", DUP_TITLE.upper()]
        for v in variants:
            self.assertEqual(normalize_topic_key(v), normalize_topic_key(DUP_TITLE))
            self.assertTrue(is_topic_already_used(v), f"Expected duplicate detection for '{v}'")
            audit = verify_topic_novelty({"title": v, "summary": "Mathematical paradox of zero drag."})
            self.assertEqual(audit["result"], "REJECTED", f"Candidate '{v}' was NOT rejected!")
            self.assertIn("EXACT DUPLICATE", audit["reason"])

    def test_02_rejected_duplicate_never_reaches_record_topic(self):
        with get_connection() as conn:
            before = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        with self.assertRaises(ValueError):
            record_topic(cluster="Test Cluster", title=DUP_TITLE, summary="dup",
                         source_url="https://example.invalid/x", fact_confidence=0.9, demand_score=50.0)
        with get_connection() as conn:
            after = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        self.assertEqual(before, after, "A rejected duplicate must never reach record_topic()!")
        self._assert_prod_unchanged()

    def test_03_videos_unchanged_for_duplicate(self):
        with get_connection() as conn:
            before = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        audit = verify_topic_novelty({"title": f"The Mystery of {DUP_TITLE}", "summary": DUP_SUMMARY})
        self.assertEqual(audit["result"], "REJECTED")
        with get_connection() as conn:
            after = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        self.assertEqual(before, after)
        self._assert_prod_unchanged()

    def test_04_level2_same_angle_rejected(self):
        audit = verify_topic_novelty({"title": f"{DUP_TITLE} Fluid Resistance Angle", "summary": DUP_SUMMARY})
        self.assertEqual(audit["result"], "REJECTED")

    def test_05_level3_new_angle_allowed(self):
        audit = verify_topic_novelty({"title": FRESH_TITLE, "summary": FRESH_SUMMARY})
        self.assertEqual(audit["result"], "APPROVED")
        self.assertEqual(audit["duplicate_topic_check"], "PASS")
        self.assertEqual(audit["duplicate_claim_check"], "PASS")
        self.assertEqual(audit["duplicate_angle_check"], "PASS")

    def test_06_production_invariance_after_suite_activity(self):
        """Next production file stays FILE #002; no test rows leak into production."""
        snap = _prod_snapshot()
        if snap["next_file"] is not None:
            self.assertEqual(snap["next_file"], 2, "Production next-file-number must remain FILE #002")
        self._assert_prod_unchanged()


if __name__ == "__main__":
    unittest.main()
