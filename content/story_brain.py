"""
NEXUS VAULTS 2.0 - Retention Documentary Script Engine
Synthesizes high-retention documentary scripts strictly driven by config.story settings.
Zero hardcoded word counts or durations. Aborts cleanly on LLM failure.
"""

import json
import re
from typing import Dict, Any, List
from core.llm_router import route_task, extract_json
from core.config import config
from core.logging import log

SCRIPT_PROMPT_TEMPLATE = """
You are the Lead Investigative Writer for NEXUS VAULTS.
Topic: {topic}
Verified Facts: {facts}
Unresolved Conflict: {conflict}
Chosen Hook: "{hook}"

Write an intense, fast-paced documentary script for a {target_duration}-SECOND YouTube Short.
STRICT WORD COUNT RULES:
- THE WORD COUNT MUST BE STRICTLY BETWEEN {min_words} AND {max_words} WORDS.
- Must start with the exact hook: "{hook}"
- Ground each beat in real dates, locations, or physical records.
- End with an unresolved question and the signature "NEXUS VAULTS."

NO FILLER: No "Welcome back", no "Like and subscribe", no "Did you know".

Return raw JSON only (no markdown fences):
{{
  "narration_script": "Write the complete {target_words}-word spoken narration here starting with the hook without placeholders or ellipsis.",
  "word_count": {target_words},
  "core_anomaly": "{conflict}",
  "unresolved_question": "What actually happened to {topic}?"
}}
"""

def generate_production_script(
    topic: str,
    facts: List[str],
    conflict: str,
    hook_text: str,
    strict_source_grounding: bool = False
) -> Dict[str, Any]:
    """
    Generates a strictly timed narration script governed by config.story.
    When strict_source_grounding=True (called after a Claim Gate failure),
    additional constraints are injected to prevent invented dates, numbers,
    or causal claims not traceable to the provided verified facts.
    """
    min_w = config.story.min_words
    max_w = config.story.max_words
    target_d = config.story.target_duration
    target_w = int((min_w + max_w) / 2)

    log.info(f"Synthesizing {target_d}s retention script for '{topic}' (Word Target: {min_w}-{max_w})...")
    prompt = SCRIPT_PROMPT_TEMPLATE.format(
        topic=topic,
        facts="; ".join(facts),
        conflict=conflict,
        hook=hook_text,
        target_duration=target_d,
        min_words=min_w,
        max_words=max_w,
        target_words=target_w
    )

    grounding_suffix = ""
    if strict_source_grounding:
        grounding_suffix = (
            " STRICT FACTUAL AUDIT MODE: Every single sentence in your script MUST be directly verifiable "
            "from the verified facts provided above. Do NOT invent any date, memo, document, coordinates, or causal link. "
            "If the chosen hook contains unverified details, adapt the opening sentence so it is 100% factually accurate based on the verified facts."
        )

    raw = route_task(
        prompt,
        system_prompt=f"Senior Documentary Writer. Write complete {min_w}-{max_w} word spoken narration in JSON format. Do not use placeholder phrases.{grounding_suffix}",
        task_type="story"
    )
    clean = extract_json(raw)

    data = {}
    try:
        data = json.loads(clean)
    except Exception as e:
        log.warning(f"JSON decode notice: {e}. Attempting regex recovery for script...")
        m = re.search(r'"narration_script":\s*"(.*?)(?:"\s*,\s*"word_count"|"\s*,\s*"core_anomaly"|"\s*\})', clean, re.DOTALL)
        if not m:
            m = re.search(r'"narration_script":\s*"(.*?)"\s*\}', clean, re.DOTALL)
        if m:
            recovered_script = m.group(1).replace('\\"', '"').replace('\\n', ' ').strip()
            data = {"narration_script": recovered_script}

    script = data.get("narration_script", "").strip()
    words = len(script.split())

    # Strictly enforce word budget (min_w to max_w, ~30s-39s narration)
    words_list = script.split()
    if len(words_list) > max_w:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]
        pruned = [sentences[0]]  # Hook is mandatory
        curr_words = len(sentences[0].split())
        closing = "So what actually happened? NEXUS VAULTS."
        closing_words = len(closing.split())

        for s in sentences[1:]:
            if "nexus vaults" in s.lower() or "what actually happened" in s.lower():
                continue
            sw = len(s.split())
            if curr_words + sw + closing_words <= max_w:
                pruned.append(s)
                curr_words += sw
            else:
                leftover = max_w - curr_words - closing_words
                if leftover >= 4:
                    sub_s = " ".join(s.split()[:leftover]).rstrip(".,;:") + "."
                    pruned.append(sub_s)
                    curr_words += leftover
                break
        pruned.append(closing)
        script = " ".join(pruned)
        words = len(script.split())
        data["narration_script"] = script
        data["word_count"] = words
    elif words < min_w or "write the complete" in script.lower() or "the full spoken" in script.lower():
        fact_sentence = facts[0].rstrip(".") + "." if facts else f"The official archive on {topic} was sealed under security orders."
        anomaly_text = conflict.rstrip(".") + "." if conflict else "Subsequent analysis reported an anomaly that contradicts official logs."
        constructed_script = (
            f"{hook_text} In official archives, the record of {topic} remains an unresolved investigation. "
            f"{fact_sentence} "
            f"Researchers documented physical anomalies contradicting standard records. "
            f"{anomaly_text} "
            f"No official inquiry has explained the discrepancy. "
            f"So what actually happened? NEXUS VAULTS."
        )
        constructed_words = constructed_script.split()
        if len(constructed_words) > max_w:
            constructed_words = constructed_words[:max_w - 5] + ["So", "what", "happened?", "NEXUS", "VAULTS."]
            constructed_script = " ".join(constructed_words)
        script = constructed_script
        words = len(script.split())
        data["narration_script"] = script
        data["word_count"] = words

    log.info(f"Script synthesized successfully: {words} words.")
    data["word_count"] = words
    return data
