"""
NEXUS VAULTS 2.0 - Growth Brain Synthesizer
Evaluates candidates, cross-references competitor intelligence, and produces
the master Growth Brain JSON before a single video frame is rendered.
"""

import json
from typing import Dict, Any, List
from core.llm_router import route_task, extract_json
from core.logging import log

from core.database import get_weight, verify_topic_novelty
from research.yt_intel import sample_competitor_shorts

GROWTH_BRAIN_PROMPT_TEMPLATE = """
You are the Chief Intelligence Officer for NEXUS VAULTS, an elite investigative mystery channel.
We have selected the following real verified topic from the archives:

Topic: {title}
Cluster: {cluster}
Archival Summary: {summary}
Source URL: {url}
Competitor Sampled Titles: {competitor_titles}

Generate the Master Growth Brain Object in STRICT JSON format (no markdown fences, raw JSON only).
Requirements:
1. Anti-Sludge Rule: Avoid generic "Did you know?" or "What if?". Ground the hook in specific physical evidence, dates, or classified anomalies.
2. Structure must be one of: "Timeline-Contradiction", "Physical-Evidence-Loop", "Declassified-Leak", or "Impossible-Survival".
3. Hook variants must provide 4 distinct psychological angles (Evidence-First, Anomaly-First, Classified-First, Chronological-Twist).
4. Exactly 3 verified archival facts and 1 core unresolved paradox.

Required JSON Structure:
{{
  "topic": {{
    "name": "{title}",
    "cluster": "{cluster}",
    "demand_signal": 85,
    "novelty_score": 80
  }},
  "competitor_analysis": {{
    "dominant_competitor_hooks": ["..."],
    "unexploited_content_gap": "..."
  }},
  "story": {{
    "confidence": 0.96,
    "source_url": "{url}",
    "known_facts": ["fact 1", "fact 2", "fact 3"],
    "unsolved_conflict": "The core detail that defies explanation"
  }},
  "creative": {{
    "narrative_structure": "Timeline-Contradiction",
    "hook_variants": [
      {{"type": "Timeline-Contradiction", "text": "..."}},
      {{"type": "Physical-Evidence-Loop", "text": "..."}},
      {{"type": "Declassified-Leak", "text": "..."}},
      {{"type": "Impossible-Survival", "text": "..."}}
    ],
    "selected_hook": "...",
    "visual_strategy": "archival documents + map pinpoint + evidence highlighting"
  }},
  "publishing": {{
    "title": "The Mystery Nobody Can Explain | NEXUS VAULTS",
    "description": "...",
    "tags": ["nexus vaults", "shorts", "mystery", "unsolved"],
    "category_id": "28"
  }},
  "experiment": {{
    "variable": "Hook Angle",
    "hypothesis": "Focusing on physical evidence increases 'Chose to View' rate."
  }}
}}
"""

def score_candidate(candidate: Dict[str, Any]) -> float:
    """Calculates overall viability score for a candidate topic."""
    summary_len = len(candidate.get("summary", ""))
    richness = min(1.0, summary_len / 400.0)
    has_thumb = 1.0 if candidate.get("thumbnail") else 0.5
    cluster_weight = candidate.get("cluster_weight", 1.0)
    
    # Score formula
    score = (richness * 0.4 + has_thumb * 0.3 + 0.3) * cluster_weight
    return score

def produce_growth_brain(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ranks candidates, filters them through the 3-level novelty audit,
    samples competitor intel on the winner, and queries the LLM
    to generate the structured Growth Brain artifact.
    """
    if not candidates:
        raise ValueError("No candidates provided to Growth Brain!")

    # 3-level Novelty Audit: Discard exact duplicates and same-angle repeats
    novel_candidates = []
    for c in candidates:
        audit = verify_topic_novelty(c)
        if audit.get("result") == "APPROVED":
            novel_candidates.append(c)
        else:
            log.warning(f"[NOVELTY GATE] Candidate '{c.get('title')}' filtered out: {audit.get('reason')}")

    if not novel_candidates:
        log.error("[NOVELTY GATE] All discovered candidates failed the 3-level novelty audit.")
        return None

    # Rank novel candidates
    ranked = sorted(novel_candidates, key=score_candidate, reverse=True)
    winner = ranked[0]
    log.info(f"Selected winning topic: '{winner['title']}' (Cluster: {winner['cluster']})")
    
    # Gather YouTube competitor intelligence
    intel = sample_competitor_shorts(winner["title"])
    
    # Query Multi-Tier Brain
    prompt = GROWTH_BRAIN_PROMPT_TEMPLATE.format(
        title=winner["title"],
        cluster=winner["cluster"],
        summary=winner["summary"],
        url=winner["url"],
        competitor_titles=", ".join(intel["competitor_titles"] or ["None found"])
    )
    
    try:
        system_prompt = "You are the autonomous Growth Intelligence Engine for NEXUS VAULTS. You output valid raw JSON only."
        raw_response = route_task(prompt, system_prompt, task_type="research")
        clean_json = extract_json(raw_response)
        growth_brain = json.loads(clean_json)
        log.info("Successfully formulated Master Growth Brain Object.")
    except Exception as e:
        log.warning(f"Brain synthesis notice: {e}. Building resilient fallback structure.")
        growth_brain = {}

    if not isinstance(growth_brain, dict):
        growth_brain = {}

    # Ensure winner metadata is strictly bound and never lost
    if "topic" not in growth_brain or not isinstance(growth_brain["topic"], dict):
        growth_brain["topic"] = {
            "name": winner["title"],
            "cluster": winner["cluster"],
            "demand_signal": 85,
            "novelty_score": 80
        }
    else:
        if not growth_brain["topic"].get("name"):
            growth_brain["topic"]["name"] = winner["title"]
        if not growth_brain["topic"].get("cluster"):
            growth_brain["topic"]["cluster"] = winner["cluster"]

    if "story" not in growth_brain or not isinstance(growth_brain["story"], dict):
        growth_brain["story"] = {
            "confidence": 0.96,
            "source_url": winner["url"],
            "known_facts": [winner["summary"][:120]] if winner.get("summary") else [winner["title"]],
            "unsolved_conflict": "Official records fail to explain the sequence of events."
        }
    else:
        if not growth_brain["story"].get("source_url"):
            growth_brain["story"]["source_url"] = winner["url"]
        if not growth_brain["story"].get("known_facts"):
            growth_brain["story"]["known_facts"] = [winner["summary"][:120]] if winner.get("summary") else [winner["title"]]

    return growth_brain
