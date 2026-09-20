"""
NEXUS VAULTS 2.0 - Lightweight Claim Verification Gate
Sits between script generation and scene planning.

PURPOSE:
  Checks each sentence in the generated narration against the Wikipedia
  source text to detect unsupported or fabricated claims before they
  reach the visual pipeline.

VERDICT LEVELS:
  SUPPORTED           - Claim is directly traceable to the source article
  PARTIALLY_SUPPORTED - Claim is implied or partially derivable from the source
  UNSUPPORTED         - Claim is not derivable from the source (hallucination risk)

DESIGN RULES:
  - This is ONE LLM call, not N calls per sentence. Fast and deterministic.
  - Returns a structured per-sentence verdict.
  - If UNSUPPORTED_COUNT > threshold -> caller requests script regeneration.
  - Does NOT rewrite the script itself — only audits it.
  - An audit score of 0 unsupported is the target; 1 partially_supported is acceptable.
"""

import json
import re
from typing import List, Dict, Any
from core.llm_router import route_task, extract_json
from core.logging import log

CLAIM_VERIFICATION_PROMPT = """\
You are a factual accuracy auditor for a documentary narration system.

SOURCE ARTICLE TEXT (Wikipedia):
\"\"\"
{source_text}
\"\"\"

GENERATED NARRATION SCRIPT:
\"\"\"
{narration}
\"\"\"

TOPIC: {topic}

For each sentence in the narration script, determine whether it is:
  SUPPORTED           — directly derivable from the source article text above
  PARTIALLY_SUPPORTED — implied or partially derivable from the source.
                        source_evidence MUST be non-null and quote the relevant passage.
                        "Partially supported" without evidence = UNSUPPORTED.
  UNSUPPORTED         — not traceable to the source (possible hallucination, date error, invented detail)

Respond ONLY with a JSON array. Each element covers one narration sentence:
[
  {{
    "sentence": "<exact sentence text>",
    "verdict": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED",
    "source_evidence": "<REQUIRED for PARTIALLY_SUPPORTED: brief quote or phrase from source. null only if UNSUPPORTED>",
    "note": "<optional: flag invented dates, exaggerated causality, combined facts, or 'possibly' turned into 'was'>"
  }},
  ...
]

Rules:
- Be strict. If a specific date, number, or causal claim has no evidence in the source text, mark it UNSUPPORTED.
- PARTIALLY_SUPPORTED without a source_evidence quote is treated as UNSUPPORTED by the pipeline.
- Do not invent supporting evidence. Quote the nearest relevant passage verbatim.
- Ignore the closing channel sign-off signature 'NEXUS VAULTS.' as it is a brand sign-off, not an empirical historical claim.
"""


def _parse_claim_verdicts(raw: str) -> List[Dict[str, Any]]:
    """Robustly parses claim verdicts from LLM output using strict=False and regex recovery."""
    if not raw:
        return []
    clean = extract_json(raw)
    verdicts: List[Dict[str, Any]] = []

    # 1. Standard JSON decode (strict=False permits unescaped newlines/control chars)
    try:
        parsed = json.loads(clean, strict=False)
        if isinstance(parsed, list):
            verdicts = parsed
        elif isinstance(parsed, dict):
            if "sentence" in parsed and "verdict" in parsed:
                verdicts = [parsed]
            else:
                for key in ("verdicts", "claims", "sentences", "results", "audit", "items"):
                    if key in parsed and isinstance(parsed[key], list):
                        verdicts = parsed[key]
                        break
                if not verdicts:
                    for v in parsed.values():
                        if isinstance(v, list) and v and isinstance(v[0], dict) and "verdict" in v[0]:
                            verdicts = v
                            break
    except Exception:
        pass

    # 2. Regex recovery for unescaped inner quotes or malformed JSON objects
    if not verdicts:
        try:
            object_matches = re.findall(r'\{([^{}]+)\}', clean or raw, re.DOTALL)
            for obj_str in object_matches:
                s_match = re.search(r'["\']sentence["\']\s*:\s*["\'](.*?)["\']\s*,\s*["\']verdict["\']', obj_str, re.DOTALL)
                sentence = s_match.group(1).strip() if s_match else ""

                v_match = re.search(r'["\']verdict["\']\s*:\s*["\'](SUPPORTED|PARTIALLY_SUPPORTED|UNSUPPORTED)["\']', obj_str, re.IGNORECASE)
                verdict = v_match.group(1).strip().upper() if v_match else ""

                e_match = re.search(r'["\']source_evidence["\']\s*:\s*(?:["\'](.*?)["\']\s*(?:,\s*["\']|(?:\n\s*\}|\}\s*$))|null)', obj_str, re.DOTALL)
                evidence = e_match.group(1).strip() if (e_match and e_match.group(1)) else None

                n_match = re.search(r'["\']note["\']\s*:\s*["\'](.*?)["\']', obj_str, re.DOTALL)
                note = n_match.group(1).strip() if n_match else ""

                if sentence and verdict:
                    verdicts.append({
                        "sentence": sentence,
                        "verdict": verdict,
                        "source_evidence": evidence,
                        "note": note
                    })
        except Exception:
            pass

    return verdicts


def verify_script_claims(
    narration: str,
    source_text: str,
    topic: str,
    max_unsupported: int = 0,
    max_partial: int = 3
) -> Dict[str, Any]:
    """
    Audits the generated narration against the Wikipedia source article.

    Args:
        narration:       The generated script text.
        source_text:     Raw Wikipedia article text for this topic.
        topic:           Topic name (for context in the LLM prompt).
        max_unsupported: Maximum UNSUPPORTED claims allowed. Default 0 (strict).
        max_partial:     Maximum PARTIALLY_SUPPORTED claims allowed. Default 3.

    Returns:
        {
          "passed": bool,
          "verdicts": List[dict],   # per-sentence audit
          "unsupported_count": int,
          "partial_count": int,
          "supported_count": int,
          "rejection_reason": str | None
        }
    """
    if not source_text or not narration:
        log.error("[CLAIM VERIFIER] Missing source text or narration — verification cannot pass without ground truth.")
        return {
            "passed": False,
            "verdicts": [],
            "unsupported_count": 0,
            "partial_count": 0,
            "supported_count": 0,
            "rejection_reason": "Missing source text or narration for factual verification",
            "skipped": False,
            "error": "Missing source text or narration"
        }

    # Allow generous article text (8k chars, ~2k tokens, well under Groq 16KB payload limit)
    source_snippet = source_text[:8000].strip()
    prompt = CLAIM_VERIFICATION_PROMPT.format(
        source_text=source_snippet,
        narration=narration.strip(),
        topic=topic
    )

    verdicts: List[Dict[str, Any]] = []
    try:
        raw = route_task(
            prompt,
            task_type="claim_verification",
            system_instruction="You are a strict factual accuracy auditor. Output only valid JSON."
        )
        verdicts = _parse_claim_verdicts(raw)

        if not verdicts:
            log.warning("[CLAIM VERIFIER] Initial claim parse yielded 0 verdicts. Retrying with secondary provider pass...")
            retry_prompt = (
                prompt
                + "\n\nCRITICAL: Output ONLY a valid JSON array of objects without Markdown formatting or unescaped quotes."
            )
            raw_retry = route_task(
                retry_prompt,
                task_type="formatting",
                system_instruction="Strict factual accuracy auditor. Raw valid JSON array only."
            )
            verdicts = _parse_claim_verdicts(raw_retry)
    except Exception as e:
        # PRD Phase 10: a failed audit is NOT a pass. Surface the failure so the
        # caller defers production instead of publishing unaudited narration.
        log.error(f"[CLAIM VERIFIER] Audit could not complete: {e} — returning FAIL (no silent pass).")
        return {
            "passed": False,
            "verdicts": [],
            "unsupported_count": 0,
            "partial_count": 0,
            "partial_without_evidence_count": 0,
            "supported_count": 0,
            "rejection_reason": f"Verification infrastructure failure: {e}",
            "skipped": False,
            "error": str(e)
        }

    # Filter out brand signature and closing rhetorical questions from factual audit
    filtered_verdicts = []
    for v in verdicts:
        s = v.get("sentence", "").strip()
        if s.rstrip(".").upper() in ("NEXUS VAULTS", "NEXUS VAULT"):
            continue
        if s.endswith("?") and v.get("verdict") == "UNSUPPORTED":
            # A closing rhetorical question ("What actually happened?", "How was his double life never caught?")
            # has no empirical truth value and is dramatic commentary rather than a factual assertion.
            continue
        filtered_verdicts.append(v)
    verdicts = filtered_verdicts

    if not verdicts:
        log.error("[CLAIM VERIFIER] Audit returned zero claim verdicts — returning FAIL.")
        return {
            "passed": False,
            "verdicts": [],
            "unsupported_count": 0,
            "partial_count": 0,
            "partial_without_evidence_count": 0,
            "supported_count": 0,
            "rejection_reason": "Audit produced 0 claim verdicts",
            "skipped": False,
            "error": "Empty verdicts"
        }

    unsupported_raw = [v for v in verdicts if v.get("verdict") == "UNSUPPORTED"]
    partial_raw = [v for v in verdicts if v.get("verdict") == "PARTIALLY_SUPPORTED"]
    supported = [v for v in verdicts if v.get("verdict") == "SUPPORTED"]

    # PARTIALLY_SUPPORTED without source_evidence is reclassified as effectively unsupported.
    # A partial claim must have the source passage quoted to be considered acceptable.
    partial_with_evidence = [v for v in partial_raw if v.get("source_evidence") and v["source_evidence"] != "null"]
    partial_without_evidence = [v for v in partial_raw if not v.get("source_evidence") or v["source_evidence"] == "null"]

    # Effective counts: partials without evidence count against the unsupported budget
    effective_unsupported = unsupported_raw + partial_without_evidence
    partial = partial_with_evidence

    passed = (len(effective_unsupported) <= max_unsupported) and (len(partial) <= max_partial)

    rejection_reason = None
    if not passed:
        parts = []
        if len(effective_unsupported) > max_unsupported:
            bad = effective_unsupported[:3]
            bad_sentences = "; ".join(f'"{v.get("sentence","")[:55]}..."' for v in bad)
            label = f"{len(unsupported_raw)} unsupported + {len(partial_without_evidence)} partial-without-evidence"
            parts.append(f"{label}: {bad_sentences}")
        if len(partial) > max_partial:
            parts.append(f"{len(partial)} PARTIALLY_SUPPORTED (with evidence) exceeds threshold ({max_partial})")
        rejection_reason = " | ".join(parts)

    # Log the full audit
    log.info(f"[CLAIM VERIFIER] {topic}: {len(supported)} supported / {len(partial)} partial / {len(effective_unsupported)} unsupported out of {len(verdicts)} claims. Result: {'PASS' if passed else 'FAIL'}")
    for v in effective_unsupported:
        log.warning(f"  [UNSUPPORTED] \"{v.get('sentence','')[:80]}\" — {v.get('note','')}")
    for v in partial:
        log.debug(f"  [PARTIAL] \"{v.get('sentence','')[:80]}\" — evidence: {v.get('source_evidence','')[:60]}")

    return {
        "passed": passed,
        "verdicts": verdicts,
        "unsupported_count": len(effective_unsupported),
        "partial_count": len(partial),
        "partial_without_evidence_count": len(partial_without_evidence),
        "supported_count": len(supported),
        "rejection_reason": rejection_reason,
        "skipped": False
    }


def fetch_wikipedia_source_text(source_url: str, topic: str) -> str:
    """
    Fetches the full plain-text extract of a Wikipedia article for claim verification.

    Uses the MediaWiki action API (prop=extracts, explaintext) so the auditor sees the
    WHOLE article — not just the intro summary. A summary-only source would make most
    true narration claims unverifiable. Falls back to the REST summary endpoint if the
    action API fails. One retry per endpoint on transient network errors.
    """
    import urllib.request
    import urllib.parse
    import time

    headers = {"User-Agent": "NEXUS-VAULTS/2.0 (claim-verifier; contact@nexusvaults.org)"}
    raw_title = source_url.split("/wiki/")[-1] if "/wiki/" in source_url else topic
    title = urllib.parse.unquote(raw_title).replace(" ", "_")

    # Primary: full plain-text extract via action API (whole article body)
    api_url = (
        f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
        f"&explaintext=1&redirects=1&format=json&formatversion=2"
        f"&titles={urllib.parse.quote(title)}"
    )
    for attempt in range(2):
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pages = data.get("query", {}).get("pages", [])
                if pages:
                    extract = pages[0].get("extract", "") or ""
                    if extract.strip():
                        return extract.strip()
        except Exception as e:
            log.debug(f"[CLAIM VERIFIER] Full-article fetch attempt {attempt + 1} for '{topic}': {e}")
            time.sleep(1)

    # Fallback: REST summary endpoint (short extract; better than no source)
    for attempt in range(2):
        try:
            api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                extract = data.get("extract", "") or ""
                if extract.strip():
                    log.warning("[CLAIM VERIFIER] Full-article extract unavailable; using intro summary only.")
                    return extract.strip()
        except Exception as e:
            log.debug(f"[CLAIM VERIFIER] Summary fetch attempt {attempt + 1} for '{topic}': {e}")
            time.sleep(1)

    return ""
