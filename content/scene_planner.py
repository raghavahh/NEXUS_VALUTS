"""
NEXUS VAULTS 2.0 - Storyboard Engine & Claim-Level Visual Director
Every narration claim maps to an explicit Visual Intent:
Claim -> Claim-Local Primary Visual Subject -> Supporting Subjects -> Visual Purpose -> Visual Type -> Exact Queries -> Motion -> Composition.
Enforces Exact Person, Exact Object, Exact Document, Exact Location, and Exact Scientific Concept Rules.
Guarantees claim-local entity extraction so the global topic NEVER leaks into individual scenes.
Driven strictly by config.scene settings from .env.
"""

import json
import re
from typing import Dict, Any, List, Tuple
from core.llm_router import route_task, extract_json
from core.config import config
from core.logging import log

VISUAL_PURPOSES = [
    "ESTABLISH_LOCATION", "IDENTIFY_PERSON", "SHOW_PRIMARY_EVIDENCE",
    "SHOW_SECONDARY_EVIDENCE", "EXPLAIN_MECHANISM", "SHOW_ROUTE",
    "SHOW_TIMELINE", "SHOW_CONTRADICTION", "HIGHLIGHT_DETAIL",
    "VISUALIZE_ABSTRACT_CONCEPT", "PROVIDE_CONTEXT", "BUILD_TENSION",
    "REVEAL_INFORMATION", "CLOSE_OUT"
]

# Temporal tokens must never become primary visual subjects ("JUNE HISTORICAL
# LOCATION", "SINCE 2004 ARCHIVAL EVIDENCE" were confirmed production sludge).
MONTH_NAMES = {
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december"
}

VISUAL_TYPES = [
    "ARCHIVAL_PHOTO", "PORTRAIT", "DOCUMENT", "MAP", "ROUTE_MAP",
    "DIAGRAM", "NEWSPAPER", "OBJECT_CLOSEUP", "TIMELINE", "ATMOSPHERIC", "GENERATED_GRAPHIC"
]

MOTION_STYLES = [
    "portrait_slow_push", "document_inspection_scroll", "map_directional_track",
    "diagram_punch_in", "archival_parallax", "hero_reveal", "horizontal_camera",
    "vertical_camera", "depth_zoom", "evidence_focus"
]

COMPOSITION_STYLES = [
    "hero_full_frame", "document_framed_elevated", "split_screen_contradiction",
    "evidence_callout", "dual_layer_framed"
]

STORYBOARD_PROMPT = """
You are the Executive Visual Director for NEXUS VAULTS 2.0.
Given this spoken script for an investigative documentary:
"{script}"

Topic: {topic}
Word Count: {word_count}
Total Duration: {total_duration} seconds.

Construct a STRICT {target_count}-SCENE VISUAL CONTRACT where every visual satisfies a CLAIM-LOCAL VISUAL INTENT and identifies an EXACT CLAIM-LOCAL PRIMARY VISUAL SUBJECT.

CRITICAL ANTI-DRIFT RULES (NON-NEGOTIABLE):
1. CLAIM-LOCAL PRIMARY VISUAL SUBJECT: The global topic MUST NOT become the scene subject.
   - If narration says "At Kitty Hawk, the 1903 Flyer measured 30 newtons of drag", primary_visual_subject MUST be "1903 Wright Flyer / Kitty Hawk" (NOT the topic).
   - If narration says "Osborne Reynolds documented boundary-layer separation", primary_visual_subject MUST be "Osborne Reynolds / Boundary-Layer Separation".
   - If narration says "Jean d'Alembert published his potential-flow theorem in Paris", primary_visual_subject MUST be "Jean le Rond d'Alembert / Potential-Flow Theorem".
2. EXACT SUBJECT ORDER:
   1. Exact Person / Historical Figure named in this beat.
   2. Exact Object / Vehicle / Telescope / Craft named in this beat.
   3. Exact Event / Experiment / Test named in this beat.
   4. Exact Location named in this beat.
   5. Exact Scientific Concept / Mechanism / Equation explained in this beat.
3. Every scene MUST assign an explicit `visual_type` (e.g. PORTRAIT, ARCHIVAL_PHOTO, DOCUMENT, DIAGRAM, OBJECT_CLOSEUP, GENERATED_GRAPHIC).
4. Exactly 3 ranked search queries focused STRICTLY on `primary_visual_subject`:
   - query_1: Specific primary entity, artifact, portrait, or document.
   - query_2: Primary subject + visual type or historical context.
   - query_3: Secondary contextual query for primary subject.

Return raw JSON only (no markdown):
{{
  "scenes": [
    {{
      "scene_id": 1,
      "start": 0.0,
      "end": 3.0,
      "narration": "exact spoken sentence fragment",
      "story_beat": "hook",
      "claim": "core claim being spoken",
      "primary_visual_subject": "exact claim-local subject",
      "supporting_visual_subjects": ["secondary term 1", "secondary term 2"],
      "visual_purpose": "SHOW_PRIMARY_EVIDENCE",
      "visual_type": "ARCHIVAL_PHOTO",
      "search_queries": ["query 1", "query 2", "query 3"],
      "motion_intent": "hero_reveal",
      "composition_intent": "hero_full_frame",
      "transition_in": "hard_cut",
      "transition_out": "hard_cut",
      "audio_intent": "major_reveal"
    }}
  ]
}}
"""

def _clean_phrase_boundaries(text: str) -> str:
    """Strips awkward leading/trailing prepositions, conjunctions, and dangling adverbs."""
    import re
    # NOTE: No duplicate entries — sets are semantically correct but duplicates signal drift
    BAD_ENDS = {"below", "later", "defined", "of", "on", "at", "in", "by", "to", "from", "for", "with", "into", "and", "or", "yet", "that", "this", "body", "steady", "then", "now", "part", "above"}
    BAD_STARTS = {"of", "in", "on", "at", "to", "for", "with", "and", "yet", "but", "while", "where", "that", "this", "from", "into"}

    words = text.split()
    while words and words[-1].lower() in BAD_ENDS:
        words.pop()
    while words and words[0].lower() in BAD_STARTS:
        words.pop(0)
    return " ".join(words)

MEASUREMENT_UNITS = {
    "km", "h", "kph", "mph", "mps", "psi", "bar", "atm", "lufs", "db", "ev", "mev", "gev", "tev",
    "meters", "miles", "feet", "inches", "tons", "tonnes", "kg", "grams", "knots", "degrees"
}

def _is_temporal_token(tok: str) -> bool:
    """Years, plain numbers, measurements, and date-like fragments are never visual subjects."""
    t_low = tok.lower()
    if t_low in MEASUREMENT_UNITS:
        return True
    if re.fullmatch(r"\d+[\d\.,]*", tok):
        return True
    if re.fullmatch(r"\d+(st|nd|rd|th)", t_low):
        return True
    if re.fullmatch(r"(1[4-9]\d{2}|20\d{2})s?", tok):
        return True
    return False

def build_archival_search_queries(primary_subj: str, vtype: str, topic: str) -> List[str]:
    """Constructs ranked search queries targeting authentic primary source media first."""
    import re
    clean_subj = re.sub(r'\(Detail \d+\)', '', primary_subj).strip()
    clean_subj = re.sub(r'\s+Archival Evidence$', '', clean_subj, flags=re.IGNORECASE).strip()
    queries = []
    if clean_subj.lower() != topic.lower():
        queries.append(f"{topic} {clean_subj}")
        queries.append(clean_subj)
    queries.append(topic)
    if vtype == "PORTRAIT":
        queries.insert(0, f"{clean_subj} portrait")
    elif vtype in ("DOCUMENT", "NEWSPAPER"):
        queries.insert(0, f"{clean_subj} document")
    elif vtype in ("ARCHIVAL_PHOTO", "OBJECT_CLOSEUP"):
        queries.insert(0, f"{clean_subj} photograph")
    elif vtype in ("MAP", "ROUTE_MAP"):
        queries.insert(0, f"{clean_subj} map")
    elif vtype in ("DIAGRAM", "GENERATED_GRAPHIC"):
        queries.insert(0, f"{clean_subj} diagram")
    return queries[:3]

def _resolve_contextual_claim_subject(claim: str, topic: str, story_context: str = "") -> Tuple[str, List[str], str, str]:
    """
    FULL STORY CONTEXT -> CURRENT CLAIM -> ENTITY / CONCEPT RESOLUTION -> PRIMARY VISUAL SUBJECT.
    Dynamically maps the narrated claim to a genuine semantic subject, supporting subjects,
    visual type, and visual purpose. Strictly eliminates noun fragments and static name lists.
    """
    clean = claim.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"').strip()
    clean_lower = clean.lower()

    # Build a topic-relative exclusion set (dynamic, never hardcoded to a specific topic)
    _topic_norm = topic.lower()
    _topic_tokens = set(re.sub(r"[^a-z\s]", "", _topic_norm).split())
    _exclusion_set = {_topic_norm, "nexus vaults"} | _topic_tokens

    STOPWORDS = {
        "the", "a", "an", "in", "on", "at", "to", "for", "with", "but", "however",
        "when", "while", "where", "why", "how", "what", "then", "now", "if", "that",
        "this", "and", "yet", "proving", "matters", "nexus", "vaults", "claimed", "claiming",
        "was", "wasn", "wasnt", "is", "isn", "isnt", "are", "aren", "arent", "were", "weren", "werent",
        "not", "part", "strange", "true", "false", "even", "still", "just", "only", "about",
        "into", "over", "under", "after", "before", "defying", "without", "been", "has", "have", "had",
        "case", "from", "became", "become", "could", "would", "might", "one", "two", "their", "there",
        "who", "which", "whom", "whose", "his", "her", "its", "our", "all", "some", "any", "each",
        "above", "below", "later", "defined", "measured", "yields", "proved", "steady", "body",
        "since", "during", "until", "around", "nearly", "early", "late", "year", "years",
        "day", "days", "month", "months", "century", "decade", "decades"
    } | MONTH_NAMES

    # 1. Historical Craft, Vehicles & Named Flight Tests
    craft_matches = re.findall(
        r"\b((?:[0-9]{4}\s+)?(?:[A-Z][a-z0-9]+\s+){0,3}(?:Flyer|Aircraft|Airplane|Plane|Glider|Ship|Vessel|Steamer|Cruiser|Submarine|Probe|Satellite|Telescope|Station|Capsule|Rover|Rocket))\b",
        clean
    )
    if craft_matches and any(k in clean_lower for k in ["flyer", "plane", "glider", "aircraft", "ship", "vessel", "steamer", "submarine", "probe", "satellite", "telescope", "station", "capsule", "rover", "rocket"]):
        craft_name = craft_matches[0].strip()
        if craft_name.lower() not in _exclusion_set:
            return craft_name, [topic, "Historical Artifact"], "OBJECT_CLOSEUP", "SHOW_PRIMARY_EVIDENCE"

    # 2. Historical Persons — supports particles: d', de, le, la, van, von, al
    name_patterns: List[str] = []
    # Pass A: names with noble/linguistic particles (d', de, le, la, van, von, al)
    name_patterns += re.findall(
        r"\b([A-Z][a-z]+(?:\s+(?:le|la|de|d['\'\u2019]|van|von|al)\s*[A-Za-z]+)+)\b",
        clean
    )
    # Pass B: plain multi-word capitalised names (e.g. Osborne Reynolds, Ludwig Prandtl)
    name_patterns += re.findall(
        r"\b([A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,}){1,3})\b",
        clean
    )
    # Deduplicate while preserving order
    seen_names: set = set()
    unique_names: List[str] = []
    for n in name_patterns:
        if n not in seen_names:
            seen_names.add(n)
            unique_names.append(n)

    filtered_names = [
        n for n in unique_names
        if n.lower() not in _exclusion_set
        and len(n.split()) >= 2
        and not n[0:3] in ("In ", "At ", "On ", "The", "Whe", "The", "Tha")
    ]

    # Expanded role / action verb list — does NOT need "mathematician" explicitly stated
    PERSON_ACTION_VERBS = {
        "mathematician", "physicist", "captain", "scientist", "inventor", "astronomer",
        "proved", "theorized", "documented", "calculated", "published",
        "derived", "showed", "proposed", "measured", "claimed", "demonstrated",
        "discovered", "established", "confirmed", "reported", "stated",
        "observed", "recorded", "designed", "built", "engineered",
        "defined", "formulated", "described", "identified", "concluded",
        "determined", "computed", "deduced", "experimented", "analyzed"
    }
    for n in filtered_names:
        if any(verb in clean_lower for verb in PERSON_ACTION_VERBS):
            return f"{n} Historical Portrait", [topic, "Historical Figure"], "PORTRAIT", "IDENTIFY_PERSON"

    # 3. Specific Locations & Facilities
    # Two-pass: (a) preposition-led "in Cambridge", (b) bare noun before known institution keywords
    loc_matches = re.findall(r"\b(?:outside|in|at|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", clean)
    # Pass B: bare location when paired with structural/institutional context
    if not loc_matches:
        if any(k in clean_lower for k in ["university", "academy", "institute", "laboratory", "lab", "centre", "center", "tunnel", "facility"]):
            loc_matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?=\s+(?:University|Academy|Institute|Laboratory|Lab|Centre|Center|Tunnel|Facility))", clean)
    LOC_STOPWORDS = {"the", "nexus", "fact", "reality", "truth", "theory", "wind", "fluid", "air", "sea"} | MONTH_NAMES
    filtered_locs = [l for l in loc_matches if l.lower() not in LOC_STOPWORDS and len(l) > 2]
    if filtered_locs and any(k in clean_lower for k in ["outside", "constructed", "built", "located", "stationed", "university", "academy", "institute", "laboratory"]):
        return f"{filtered_locs[0]} Historical Location", [topic], "ARCHIVAL_PHOTO", "ESTABLISH_LOCATION"

    # 4. Historical Documents & Archival Treatises
    if any(k in clean_lower for k in ["treatise", "paper", "manuscript", "logbook", "inquiry", "patent"]):
        # Dynamically extract any capitalised location in the claim — not a hardcoded whitelist
        dyn_locs = re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b", clean)
        dyn_locs = [l for l in dyn_locs if l.lower() not in _exclusion_set | LOC_STOPWORDS and len(l.split()[0]) > 2]
        loc_str = f"{dyn_locs[0]} " if dyn_locs else (f"{filtered_locs[0]} " if filtered_locs else "")
        years = re.findall(r"\b(1[6-9]\d{2}|20\d{2})\b", clean)
        if years:
            return f"{years[0]} {loc_str}Archival Treatise & Proof", [topic, "Archival Manuscript"], "DOCUMENT", "SHOW_PRIMARY_EVIDENCE"
        return f"{loc_str}Archival Treatise & Records", [topic, "Primary Evidence"], "DOCUMENT", "SHOW_PRIMARY_EVIDENCE"

    # 5. Testing Apparatus & Facilities
    if any(k in clean_lower for k in ["wind-tunnel", "wind tunnel", "wind\u2011tunnel", "apparatus", "testing facility", "accelerator"]):
        if any(k in clean_lower for k in ["wind-tunnel", "wind tunnel", "wind\u2011tunnel"]):
            return "Aeronautical Wind-Tunnel Testing Apparatus", ["Fluid Dynamics", "Aerodynamic Testing"], "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"
        return f"{topic} Experimental Testing Apparatus", [topic, "Scientific Equipment"], "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"

    # 6. Paradox / Theoretical Resolution
    if any(k in clean_lower for k in ["paradox was resolved", "resolved by", "resolution", "persists"]):
        res_tokens = [w.capitalize() for w in re.findall(r"[a-z]{4,}", clean_lower) if w not in _exclusion_set and w not in STOPWORDS][:2]
        res_suffix = f": {' '.join(res_tokens)}" if res_tokens else ""
        return f"{topic} Theoretical Resolution{res_suffix}", [topic, "Scientific Theory"], "DIAGRAM", "REVEAL_INFORMATION"

    # 7. Scientific Concepts & Phenomena
    if any(k in clean_lower for k in ["boundary-layer", "boundary layer", "separation regime"]):
        return "Boundary-Layer Separation & Wake Deflection", ["Fluid Dynamics", "Viscous Flow"], "DIAGRAM", "EXPLAIN_MECHANISM"
    if any(k in clean_lower for k in ["viscosity", "shear stress"]):
        return "Fluid Viscosity & Shear Stress Mechanism", ["Physics Analysis", "Physical Dynamics"], "DIAGRAM", "EXPLAIN_MECHANISM"
    if any(k in clean_lower for k in ["fluid mechanics", "flow separation"]):
        return f"{topic} Physical Mechanism Analysis", [topic, "Physics Analysis"], "DIAGRAM", "EXPLAIN_MECHANISM"
    if any(k in clean_lower for k in ["potential flow", "potential-flow", "inviscid"]):
        return "Inviscid Potential Flow Streamline Theorem", ["Ideal Fluid Flow", "Theoretical Physics"], "DIAGRAM", "EXPLAIN_MECHANISM"
    if any(k in clean_lower for k in ["drag force", "drag steady body", "substantial drag", "resistance", "friction"]):
        return f"{topic} Force & Resistance Dynamics", [topic, "Physical Dynamics"], "DIAGRAM", "EXPLAIN_MECHANISM"

    # 8. Remaining Locations if any
    if filtered_locs:
        return f"{filtered_locs[0]} Historical Location", [topic], "ARCHIVAL_PHOTO", "ESTABLISH_LOCATION"

    # 9. Domain Specialties (Maritime, Classified History)
    if any(k in clean_lower for k in ["pack ice", "ice pack", "frozen in ice", "arctic ocean", "beaufort"]):
        return "Arctic Pack Ice Field & Maritime Route", ["Polar Navigation", "Pack Ice"], "ARCHIVAL_PHOTO", "ESTABLISH_LOCATION"
    if any(k in clean_lower for k in ["furnace", "boiler", "coal", "firebox", "steam propulsion"]):
        return "Ship Coal Furnace & Boiler Firebox", ["Steam Propulsion", "Thermal Combustion"], "DIAGRAM", "EXPLAIN_MECHANISM"
    if any(k in clean_lower for k in ["ghost ship", "abandoned crew", "derelict", "vanished", "crew vanished"]):
        return "Derelict Maritime Sighting & Abandonment", ["Ghost Ship", "Maritime Archive"], "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"
    if any(k in clean_lower for k in ["declassified", "mkultra", "cia", "intelligence", "covert"]):
        return "Declassified Government Intelligence Records", ["Classified Archives", "Investigation Dossier"], "DOCUMENT", "SHOW_PRIMARY_EVIDENCE"

    # 10. Semantic Stopword & Fragment Cleaning (Prevents awkward sentence snippets)
    # Fallback: Extract first 3-4 significant words from the claim itself
    words_filtered = [
        w for w in re.findall(r"\b[A-Za-z0-9\-']+\b", clean)
        if w.lower() not in STOPWORDS and not _is_temporal_token(w)
    ]
    while words_filtered and len(words_filtered[0]) <= 2:
        words_filtered.pop(0)

    cleaned_candidate = _clean_phrase_boundaries(" ".join(words_filtered[:4]).title())
    bad_prefixes = ("Since", "During", "Until", "Around", "Nearly", "Shattering", "Causing", "After", "Before")

    if len(cleaned_candidate.split()) >= 2 and not any(cleaned_candidate.startswith(bp) for bp in bad_prefixes):
        return cleaned_candidate, [topic], "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"

    # Fallback to qualified topic facet (NEVER bare topic alone)
    return f"{topic} Investigation Focus", [topic], "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"

def _determine_visual_type_and_purpose(claim: str, topic: str, story_context: str = "") -> Tuple[str, str]:
    """
    Determine the visual type and visual purpose for a given claim.
    Returns a tuple of (visual_type, visual_purpose).
    Simplified implementation - to be enhanced based on requirements.
    """
    claim_lower = claim.lower().strip()
    
    # Handle person patterns
    if re.search(r"\b(dr|prof|professor|doctor|rev|reverend|fr|father|sr|sister|ms|miss|mrs|mx)\.?\s+[A-Z][a-z]", claim, re.I):
        return ("PORTRAIT", "IDENTIFY_PERSON")
    
    # Handle locations
    if re.search(r"\b([A-Z][a-z]+(?:[\s-][A-Z][a-z]+)+)\b", claim):
        return ("ARCHIVAL_PHOTO", "ESTABLISH_LOCATION")
    
    # Handle dates/years
    if re.search(r"\b(1[0-9]{3}|2[0-9]{3})\b", claim):
        return ("ARCHIVAL_PHOTO", "PROVIDE_CONTEXT")
    
    # Handle measurements
    if re.search(r"\b\d+\.?\d*\s*(mm|cm|m|km|in|ft|yd|mi|mph|kph)\b", claim, re.I):
        return ("ARCHIVAL_PHOTO", "PROVIDE_CONTEXT")
    
    # Handle scientific concepts
    if any(k in claim_lower for k in ["reynolds number", "boundary layer", "viscosity", "potential flow", "drag force"]):
        return ("DIAGRAM", "EXPLAIN_MECHANISM")
    
    # Default fallback
    return ("ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE")

def _extract_claim_subject(claim: str, topic: str) -> Tuple[str, List[str], str, str]:
    """Public interface ensuring full backwards-compatibility with regression tests."""
    return _resolve_contextual_claim_subject(claim, topic)

def _split_into_scene_claims(script: str, num_scenes: int, topic: str) -> List[str]:
    """
    Divides script into num_scenes distinct claims at natural clause/sentence boundaries.
    Guarantees entities like 'New York' or 'Pack Ice' are never fractured across scene boundaries.
    """
    clean = re.sub(r'\s+', ' ', script).strip()
    # Protect compound entities and noble/particle names from awkward mid-word splitting
    protected = re.sub(
        r"\b([A-Z][a-z]+(?:\s+(?:le|la|de|d['\'\u2019]|van|von|al)\s*[A-Za-z]+)+)\b",
        lambda m: m.group(1).replace(" ", "_"),
        clean
    )
    protected = re.sub(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", lambda m: m.group(1).replace(" ", "_"), protected)
    
    parts = [p.strip().replace("_", " ")
             for p in re.split(r'(?<=[.!?])\s+|(?<=[,;])\s+|\s+(?:while|yet|however|proving|where)\s+', protected) if p.strip()]
    meaningful = [p for p in parts if p.lower() not in ("nexus vaults.", "nexus vaults") and len(p.split()) >= 2]
    if not meaningful:
        meaningful = parts or [topic]

    while len(meaningful) > num_scenes:
        # Merge shortest adjacent pair
        min_len = 999
        min_idx = 0
        for idx in range(len(meaningful) - 1):
            comb = len(meaningful[idx].split()) + len(meaningful[idx+1].split())
            if comb < min_len:
                min_len = comb
                min_idx = idx
        merged = meaningful[min_idx] + ", " + meaningful[min_idx+1]
        meaningful = meaningful[:min_idx] + [merged] + meaningful[min_idx+2:]

    while len(meaningful) < num_scenes:
        longest_idx = max(range(len(meaningful)), key=lambda idx: len(meaningful[idx].split()))
        words = meaningful[longest_idx].split()
        if len(words) >= 5:
            # Find best split point near the middle that doesn't split between 'New' and 'York'
            mid = len(words) // 2
            if mid < len(words) - 1 and words[mid].lower() in ("new", "saint", "san", "mount", "port"):
                mid += 1
            h1 = " ".join(words[:mid])
            h2 = " ".join(words[mid:])
            meaningful = meaningful[:longest_idx] + [h1, h2] + meaningful[longest_idx+1:]
        else:
            break

    while len(meaningful) < num_scenes:
        meaningful.append(f"{topic} Key Archival Discovery")

    return meaningful[:num_scenes]

def generate_storyboard(script: str, topic: str, total_duration: float) -> List[Dict[str, Any]]:
    """Generates the claim-linked storyboard according to config.scene with exact claim-local primary visual subjects."""
    min_count = config.scene.min_count
    target_count = config.scene.target_count
    max_count = config.scene.max_count
    min_dur = config.scene.min_duration
    max_dur = config.scene.max_duration
    words = script.split()

    prompt = STORYBOARD_PROMPT.format(
        script=script,
        topic=topic,
        word_count=len(words),
        total_duration=round(total_duration, 2),
        min_count=min_count,
        target_count=target_count,
        max_count=max_count,
        min_duration=min_dur,
        max_duration=max_dur
    )

    try:
        raw_response = route_task(prompt, task_type="story", system_instruction="You are an expert investigative documentary visual director. Output strictly valid JSON.")
        clean = extract_json(raw_response)
        data = json.loads(clean)
        scenes = data if isinstance(data, list) else data.get("scenes", [])
        if min_count <= len(scenes) <= max_count:
            # Check for topic drift in LLM output: if >50% of scenes have the bare topic as primary subject, re-extract
            topic_clean = topic.lower().split(":")[0].strip()
            drift_count = sum(1 for sc in scenes if sc.get("primary_visual_subject", "").lower() == topic_clean)
            if drift_count <= 2:
                for idx, sc in enumerate(scenes):
                    if not sc.get("primary_visual_subject") or sc["primary_visual_subject"].lower() == topic_clean:
                        p_subj, supp, vtype, purp = _extract_claim_subject(sc.get("narration", sc.get("claim", topic)), topic)
                        sc["primary_visual_subject"] = p_subj
                        sc["supporting_visual_subjects"] = supp
                        sc["visual_type"] = vtype
                        sc["visual_purpose"] = purp

                    p_subj = sc["primary_visual_subject"]
                    llm_queries = sc.get("search_queries")
                    built_queries = build_archival_search_queries(p_subj, vtype, topic)
                    if llm_queries and isinstance(llm_queries, list) and all(isinstance(q, str) and len(q.strip()) >= 3 for q in llm_queries):
                        combined = [q.strip() for q in llm_queries if q.strip()]
                        for b in built_queries:
                            if b not in combined:
                                combined.append(b)
                        sc["search_queries"] = combined
                    else:
                        sc["search_queries"] = built_queries
                    sc["storyboard_source"] = "AI"
                    sc["motion_style"] = sc.get("motion_intent", "hero_reveal")
                    sc["duration"] = round(sc.get("end", 0.0) - sc.get("start", 0.0), 2)

                log.info(f"Storyboard successfully created via cloud AI: {len(scenes)} scenes with Claim-Local Primary Subjects.")
                return scenes
            else:
                log.warning(f"Cloud storyboard suffered topic drift ({drift_count}/{len(scenes)} inherited topic). Engaging claim-local extractor.")
    except Exception as e:
        log.warning(f"Cloud storyboard generation exception: {e}. Assembling exact-subject dynamic storyboard.")

    # Script-aware dynamic fallback guaranteeing claim-local subjects across all scenes
    scene_claims = _split_into_scene_claims(script, target_count, topic)
    num_scenes = len(scene_claims)
    slice_dur = round(total_duration / float(num_scenes), 2)

    scenes = []
    seen_subjects = set()
    for i in range(num_scenes):
        start = round(i * slice_dur, 2)
        end = round((i + 1) * slice_dur, 2) if i < num_scenes - 1 else round(total_duration, 2)
        claim_text = scene_claims[i]

        primary_subj, supp_subjs, vtype, purpose = _extract_claim_subject(claim_text, topic)

        # Enforce distinct subject per scene
        if primary_subj in seen_subjects:
            primary_subj = f"{primary_subj} (Detail {i+1})"
        seen_subjects.add(primary_subj)

        motion = "portrait_slow_push" if vtype == "PORTRAIT" else (
            "document_inspection_scroll" if vtype in ("DOCUMENT", "NEWSPAPER") else (
                "diagram_punch_in" if vtype in ("DIAGRAM", "GENERATED_GRAPHIC") else "hero_reveal"
            )
        )
        comp = "hero_full_frame" if vtype in ("ARCHIVAL_PHOTO", "PORTRAIT") else "dual_layer_framed"
        a_intent = "major_reveal" if i == 0 or i == num_scenes - 1 else ("evidence_hit" if vtype in ("DOCUMENT", "PORTRAIT") else "normal")

        queries = build_archival_search_queries(primary_subj, vtype, topic)

        scenes.append({
            "scene_id": i + 1,
            "storyboard_source": "FALLBACK",
            "start": start,
            "end": end,
            "duration": round(end - start, 2),
            "narration": claim_text,
            "story_beat": "hook" if i == 0 else ("evidence" if i < num_scenes - 2 else "conclusion"),
            "claim": claim_text,
            "primary_visual_subject": primary_subj,
            "supporting_visual_subjects": supp_subjs,
            "visual_purpose": purpose,
            "visual_type": vtype,
            "search_queries": queries,
            "motion_intent": motion,
            "motion_style": motion,
            "composition_intent": comp,
            "transition_in": "hard_cut",
            "transition_out": "hard_cut",
            "audio_intent": a_intent
        })

    log.info(f"Generated {len(scenes)}-scene claim-local exact storyboard ({total_duration:.2f}s).")
    return scenes
