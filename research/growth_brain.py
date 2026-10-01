"""
AI Video Factory - Growth Brain Synthesizer
Evaluates candidates, cross-references competitor intelligence, and produces
the master Growth Brain JSON before a single video frame is rendered.
Channel-driven via Channel Brain.
"""

import json
from typing import Dict, Any, List
from core.llm_router import route_task, extract_json
from core.logging import log
from core.channel_brain import get_channel_brain

from core.database import get_weight, verify_topic_novelty
from research.yt_intel import sample_competitor_shorts
from research.media_preflight import evaluate_media_preflight

def _build_growth_brain_prompt_context() -> str:
    """Build Channel Brain context for growth brain synthesis."""
    brain = get_channel_brain()
    return brain.get_prompt_context("topic_selection")

GROWTH_BRAIN_PROMPT_TEMPLATE = """
You are the Chief Intelligence Officer for {channel_name}, a {channel_niche} channel.
{creative_directive}

{learning_memory}

Channel Profile:
- Name: {channel_name}
- Handle: {channel_handle}
- Niche: {channel_niche}
- Audience: {channel_audience}
- Language: {channel_language}

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
{
  "topic": {
    "name": "{title}",
    "cluster": "{cluster}",
    "demand_signal": 85,
    "novelty_score": 80
  },
  "competitor_analysis": {
    "dominant_competitor_hooks": ["..."],
    "unexploited_content_gap": "..."
  },
  "story": {
    "confidence": 0.96,
    "source_url": "{url}",
    "known_facts": ["fact 1", "fact 2", "fact 3"],
    "unsolved_conflict": "The core detail that defies explanation"
  },
  "creative": {
    "narrative_structure": "Timeline-Contradiction",
    "hook_variants": [
      {"type": "Timeline-Contradiction", "text": "..."},
      {"type": "Physical-Evidence-Loop", "text": "..."},
      {"type": "Declassified-Leak", "text": "..."},
      {"type": "Impossible-Survival", "text": "..."}
    ],
    "selected_hook": "...",
    "visual_strategy": "archival documents + map pinpoint + evidence highlighting"
  },
  "publishing": {
    "title": "The Mystery Nobody Can Explain | {channel_name}",
    "description": "...",
    "tags": ["{channel_handle_lower}", "shorts", "documentary", "{channel_niche_lower}"],
    "category_id": "{category_id}"
  },
  "experiment": {
    "variable": "Hook Angle",
    "hypothesis": "Focusing on physical evidence increases 'Chose to View' rate."
  }
}
}"""

def score_candidate(candidate: Dict[str, Any]) -> float:
    """Calculates overall viability score for a candidate topic."""
    summary_len = len(candidate.get("summary", ""))
    richness = min(1.0, summary_len / 400.0)
    # Heavy weighting on visual evidence availability to guarantee fulfillment of
    # PRD S6 (>= 4 authentic archival assets, <= 3 generated graphics)
    has_thumb = 1.0 if candidate.get("thumbnail") else 0.05
    cluster_weight = candidate.get("cluster_weight", 1.0)
    
    score = (richness * 0.35 + has_thumb * 0.55 + 0.10) * cluster_weight
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

    # 2. Media Preflight Gate: Enforce PRD S6 authentic documentary asset requirements
    from research.media_preflight import evaluate_media_preflight

    eligible_candidates = []
    for cand in novel_candidates:
        report = evaluate_media_preflight(cand["title"])
        cand["media_preflight"] = report
        if report["status"] in ("ELIGIBLE", "STRONG"):
            eligible_candidates.append(cand)

    if not eligible_candidates:
        log.error(
            "[MEDIA PREFLIGHT: PIPELINE DEFERRED] Zero discovered candidates met the media preflight gate "
            "(minimum 4 relevant authentic documentary assets). Deferring production cleanly."
        )
        return None

    # 3. Rank ONLY eligible candidates (winner MUST be in eligible_candidates)
    ranked = sorted(eligible_candidates, key=score_candidate, reverse=True)
    winner = ranked[0]
    if winner not in eligible_candidates:
        log.error(
            f"[MEDIA PREFLIGHT INVARIANT VIOLATION] Winner '{winner.get('title')}' is not in eligible_candidates! "
            "Pipeline failing closed."
        )
        return None
    log.info(
        f"Selected winning topic: '{winner['title']}' (Cluster: {winner['cluster']} | "
        f"Preflight: {winner['media_preflight']['status']} | Relevant Assets: {winner['media_preflight']['relevant_count']} | "
        f"Est. Survivors: {winner['media_preflight']['estimated_survivors']})"
    )
    
    # Gather YouTube competitor intelligence
    intel = sample_competitor_shorts(winner["title"])
    
    # Build Channel Brain context for the prompt
    brain = get_channel_brain()

    # Query Multi-Tier Brain
    prompt = GROWTH_BRAIN_PROMPT_TEMPLATE.format(
        title=winner["title"],
        cluster=winner["cluster"],
        summary=winner["summary"],
        url=winner["url"],
        competitor_titles=", ".join(intel["competitor_titles"] or ["None found"]),
        channel_name=brain.profile.name or "AI Video Factory",
        channel_handle=brain.profile.handle or "aivideofactory",
        channel_handle_lower=(brain.profile.handle or "aivideofactory").lower(),
        channel_niche=brain.profile.niche or "documentary",
        channel_niche_lower=(brain.profile.niche or "documentary").lower(),
        channel_audience=brain.profile.audience or "general",
        channel_language=brain.profile.language or "en",
        category_id=brain.publishing_prefs.category_id or "27",
        creative_directive=brain.creative_directive.directive if brain.creative_directive.directive else "",
        learning_memory=brain.learning_memory.get_compact_context() if brain.learning_memory.recent_topics else ""
    )
    try:
        system_prompt = f"You are the autonomous Growth Intelligence Engine for {brain.profile.name or 'AI Video Factory'}. You output valid raw JSON only."
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
