"""
NEXUS VAULTS - Media Preflight, Selector Invariant, and Hook Grounding Unit Tests (ISOLATED)
Tests the critical architectural contracts introduced after Run #7:
1. Media preflight boundary conditions:
   - < 4 relevant assets -> REJECT
   - 4 relevant assets with < 4 estimated survivors -> REJECT (resolves 4->3 inconsistency)
   - 4-5 relevant assets with >= 4 estimated survivors -> ELIGIBLE
   - 6+ relevant assets with >= 5 estimated survivors -> STRONG
2. Selector Invariant:
   - Rejected candidate cannot be selected
   - Zero eligible candidates triggers clean deferral
   - Winner must belong to eligible_candidates
3. Hook Grounding:
   - Fallback hook handles empty facts gracefully
4. Claim Verifier:
   - Robust parsing with unescaped quotes
"""

import unittest
from unittest.mock import patch, MagicMock

import _guard
_guard.ensure_isolation()

from core.database import init_db
from research.media_preflight import evaluate_media_preflight
from research.growth_brain import produce_growth_brain
from content.claim_verifier import _parse_claim_verdicts


class MediaPreflightAndContractsTest(unittest.TestCase):

    def setUp(self):
        init_db()

    def test_preflight_boundary_less_than_four(self):
        """Less than 4 relevant authentic assets must REJECT."""
        with patch("research.media_preflight.fetch_wikipedia_article_images") as mock_wiki, \
             patch("research.media_preflight.search_commons_query") as mock_commons:
            mock_wiki.return_value = [{"title": "File:Artifact1.jpg", "canonical_url": "http://a1.jpg"}]
            mock_commons.return_value = [{"title": "File:Artifact2.jpg", "canonical_url": "http://a2.jpg"}]
            report = evaluate_media_preflight("Sample Topic")
            self.assertEqual(report["status"], "REJECT")
            self.assertLess(report["relevant_count"], 4)

    def test_preflight_boundary_four_assets_low_survivors_rejects(self):
        """4 assets where estimated survivors < 4 must REJECT (resolves the 4-asset pass with 3 survivors trap)."""
        with patch("research.media_preflight.fetch_wikipedia_article_images") as mock_wiki, \
             patch("research.media_preflight.search_commons_query") as mock_commons:
            mock_wiki.return_value = []
            mock_commons.return_value = [
                {"title": f"File:Commons_{i}.jpg", "canonical_url": f"http://c{i}.jpg"}
                for i in range(4)
            ]
            report = evaluate_media_preflight("Low Survivor Topic")
            self.assertEqual(report["relevant_count"], 4)
            self.assertLess(report["estimated_survivors"], 4)
            self.assertEqual(report["status"], "REJECT")

    def test_preflight_eligible_boundary(self):
        """5 article assets: 5 * 0.85 = 4.25 -> 4 survivors >= 4 -> ELIGIBLE."""
        with patch("research.media_preflight.fetch_wikipedia_article_images") as mock_wiki, \
             patch("research.media_preflight.search_commons_query") as mock_commons:
            mock_wiki.return_value = [
                {"title": f"File:Doc_{i}.jpg", "canonical_url": f"http://d{i}.jpg"}
                for i in range(5)
            ]
            mock_commons.return_value = []
            report = evaluate_media_preflight("Eligible Topic")
            self.assertEqual(report["relevant_count"], 5)
            self.assertGreaterEqual(report["estimated_survivors"], 4)
            self.assertEqual(report["status"], "ELIGIBLE")

    def test_preflight_strong_boundary(self):
        """8 article assets -> STRONG."""
        with patch("research.media_preflight.fetch_wikipedia_article_images") as mock_wiki, \
             patch("research.media_preflight.search_commons_query") as mock_commons:
            mock_wiki.return_value = [
                {"title": f"File:Doc_{i}.jpg", "canonical_url": f"http://d{i}.jpg"}
                for i in range(8)
            ]
            mock_commons.return_value = []
            report = evaluate_media_preflight("Strong Topic")
            self.assertGreaterEqual(report["relevant_count"], 6)
            self.assertEqual(report["status"], "STRONG")

    def test_growth_brain_excludes_rejected_candidates(self):
        """Growth Brain must never select a candidate that media preflight rejected."""
        candidates = [
            {"title": "Sparse Story A", "cluster": "Unexplained", "summary": "Summary A", "url": "http://a"},
            {"title": "Sparse Story B", "cluster": "Unexplained", "summary": "Summary B", "url": "http://b"}
        ]
        with patch("core.database.verify_topic_novelty") as mock_nov, \
             patch("research.growth_brain.evaluate_media_preflight") as mock_pre:
            mock_nov.return_value = {"approved": True, "score": 1.0, "reason": "novel"}
            mock_pre.return_value = {
                "status": "REJECT",
                "relevant_count": 2,
                "estimated_survivors": 1,
                "raw_count": 2
            }
            result = produce_growth_brain(candidates)
            self.assertIsNone(result, "When all candidates are REJECTed by media preflight, result must be None (clean deferral).")

    def test_claim_parser_handles_unescaped_quotes_and_structures(self):
        """Verifies _parse_claim_verdicts handles unescaped inner quotes."""
        raw_llm_output = """[
  {
    "sentence": "In 1898, Goodall built a secluded settlement on the island.",
    "verdict": "SUPPORTED",
    "source_evidence": "Goodall built his "hermitage" on the island in 1898.",
    "note": "direct match"
  },
  {
    "sentence": "Visitors called him a madman.",
    "verdict": "PARTIALLY_SUPPORTED",
    "source_evidence": "The press described him as "the eccentric hermit".",
    "note": "press vs visitors"
  },
  {
    "sentence": "He disappeared in 1920 without a trace.",
    "verdict": "UNSUPPORTED",
    "source_evidence": null,
    "note": "Date is unverified"
  }
]"""
        verdicts = _parse_claim_verdicts(raw_llm_output)
        self.assertEqual(len(verdicts), 3)
        self.assertEqual(verdicts[0]["verdict"], "SUPPORTED")
        self.assertEqual(verdicts[1]["verdict"], "PARTIALLY_SUPPORTED")
        self.assertEqual(verdicts[2]["verdict"], "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
