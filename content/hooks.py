"""
NEXUS VAULTS 2.0 - The God Hook Engine
Generates candidate hooks across curiosity categories.
Scored and selected via config.hook parameters.
Zero fake fallback content: clean abortion if all AI providers fail.
"""

import json
import re
from typing import List, Dict, Any
from core.llm_router import route_task, extract_json
from core.database import get_weight
from core.config import config
from core.logging import log


HOOK_CATEGORIES = [
    "CONTRADICTION",
    "IMPOSSIBLE DETAIL",
    "HIDDEN EVIDENCE",
    "COUNTDOWN",
    "LOCATION"
]

HOOK_PROMPT_TEMPLATE = """
You are the master retention critic for NEXUS VAULTS.
Topic: {topic}
Verified Facts: {facts}
Core Anomaly: {conflict}

Generate {count} HIGH-RETENTION DOCUMENTARY HOOKS across the curiosity categories:
- CONTRADICTION hooks ("The official timeline says X, but...")
- IMPOSSIBLE DETAIL hooks ("The strange part wasn't that...")
- HIDDEN EVIDENCE hooks ("Documented records revealed...")
- COUNTDOWN hooks ("Within hours, investigators uncovered...")
- LOCATION hooks ("At the exact coordinates where...")

STRICT RULES:
1. NEVER start with "Did you know", "Imagine if", or clickbait lies.
2. Ground each hook strictly in the Verified Facts provided above.
3. NEVER invent dates, memos, classified documents, coordinates, or names not explicitly stated in the Verified Facts.
4. Keep each hook under 16 words. Punchy and cinematic.

Return raw JSON only (no markdown fences):
{{
  "candidate_hooks": [
    {{"category": "CONTRADICTION", "hook": "..."}}
  ]
}}
"""

def generate_and_score_hooks(topic: str, facts: List[str], conflict: str, source_context: str = "") -> Dict[str, Any]:
    """Generates candidate hooks, scores them, and selects the winning hook."""
    count = config.hook.candidate_count
    log.info(f"Generating {count} candidate hooks for: '{topic}'")
    facts_str = "; ".join(facts)
    if source_context:
        facts_str += f"\nDocumented Source Excerpt: {source_context[:1200].strip()}"
    prompt = HOOK_PROMPT_TEMPLATE.format(
        topic=topic,
        facts=facts_str,
        conflict=conflict,
        count=count
    )

    raw = route_task(prompt, system_prompt="Critic & Hook Architect. Raw JSON only.", task_type="hook")
    clean = extract_json(raw)

    try:
        data = json.loads(clean)
        candidates = data.get("candidate_hooks", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception as e:
        log.warning(f"Failed to parse hook response directly: {e}. Attempting regex recovery.")
        candidates = []
        for m in re.finditer(r'\{[^{}]*"hook":\s*"([^"]+)"[^{}]*\}', raw):
            hook_text = m.group(1)
            cat_match = re.search(r'"category":\s*"([^"]+)"', m.group(0))
            cat = cat_match.group(1) if cat_match else "CONTRADICTION"
            candidates.append({"category": cat, "hook": hook_text})
        if not candidates:
            raise RuntimeError(f"Hook generation failed: No valid candidate hooks returned by AI provider for topic '{topic}'.")

    # Clean and normalize quotes across all candidate hooks
    for c in candidates:
        if isinstance(c, dict) and "hook" in c:
            c["hook"] = c["hook"].replace('"', "'").strip()

    # Score each hook: Historical weight * brevity bonus
    scored_hooks = []
    sc_lower = source_context.lower() if source_context else ""
    suspicious = ["memo", "logbook", "cipher", "blueprint", "declassified", "sealed admiralty", "telegram", "diaries", "diary", "classified memo"]

    for item in candidates:
        cat = item.get("category", "CONTRADICTION")
        text = item.get("hook", "").strip()
        words = len(text.split())
        base_w = get_weight(f"hook:{cat}", 1.1)

        # Brevity bonus: 10-15 words is the golden ratio for Shorts retention
        if 8 <= words <= 16:
            mult = 1.3
        elif words < 8:
            mult = 0.95
        else:
            mult = 0.75

        score = base_w * mult

        # Factual grounding penalty: if hook invents document/memo types absent from source, heavily down-rank
        if sc_lower and any(w in text.lower() and w not in sc_lower for w in suspicious):
            score *= 0.15

        scored_hooks.append((score, {"category": cat, "text": text}))

    scored_hooks.sort(key=lambda x: x[0], reverse=True)
    winner_score, winner = scored_hooks[0]
    winner["all_candidates"] = [h[1] for h in scored_hooks]
    min_score = config.hook.min_score
    if winner_score < min_score:
        log.warning(f"Top hook score ({winner_score:.2f}) below configured minimum ({min_score}). Candidate accepted with warning.")
    log.info(f"Top Hook Selected [{winner['category']}]: \"{winner['text']}\" (Score: {winner_score:.2f})")
    return winner
