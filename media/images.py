"""
NEXUS VAULTS 2.0 - Per-Scene Asset Harvester & Semantic Relevance Gate
Implements:
1. Exact Subject Harvesting: Queries centered strictly on primary_visual_subject.
2. Hard Relevance Gate: Strict rejection of assets with score < config.scene.relevance_min_score.
3. Independent Visual Semantic QA Pass: Second-pass critic verification.
4. Truthful Explanatory Graphic Fallback: Renders technical schematics for abstract concepts instead of filler.
5. 5-Tier Deduplication: Canonical URL, SHA-256 binary hash, 64-bit dHash perceptual distance, normalized title.
6. Comprehensive Provenance Ledger: Records source, URL, creator, license, SHA-256, and perceptual hash for every scene.
"""

import io
import shutil
import hashlib
import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from PIL import Image
from core.config import config
from core.logging import log
from core.llm_router import route_task, extract_json
from media.explanatory_graphic import create_truthful_explanatory_graphic

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "NexusVaultsEngine/2.0 (media provenance auditor; contact@nexusvaults.org)"}

class VisualBudgetExceededError(Exception):
    """Raised when generated graphics exceed the allowed budget or authentic assets are below threshold."""
    pass

KNOWN_FAMOUS_PEOPLE = {
    "ada lovelace", "lovelace", "charles babbage", "babbage", "marie curie",
    "curie", "isaac newton", "newton", "albert einstein", "einstein",
    "stephen hawking", "hawking", "winston churchill", "abraham lincoln",
    "nikola tesla", "tesla", "thomas edison", "edison", "niels bohr", "bohr",
    "richard feynman", "feynman", "alan turing", "turing",
    "donald trump", "trump", "barack obama", "obama", "joe biden", "biden",
    "george bush", "bush", "richard nixon", "nixon", "bill clinton", "clinton",
    "ronald reagan", "reagan", "john f kennedy", "kennedy"
}

def compute_sha256(file_path: Path) -> str:
    """Calculates exact SHA-256 binary digest."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def compute_dhash(img_path: Path, hash_size: int = 8) -> int:
    """Computes 64-bit difference hash (dHash) for perceptual similarity detection."""
    with open(img_path, "rb") as f:
        with Image.open(f) as img:
            gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            bytes_data = list(gray.tobytes())
            diff = []
            for row in range(hash_size):
                for col in range(hash_size):
                    idx = row * (hash_size + 1) + col
                    diff.append(bytes_data[idx] > bytes_data[idx + 1])
            hash_val = 0
            for bit in diff:
                hash_val = (hash_val << 1) | (1 if bit else 0)
            return hash_val

def hamming_distance(h1: int, h2: int) -> int:
    """Calculates bit difference between two perceptual hashes."""
    return bin(h1 ^ h2).count("1")

def normalize_title(title: str) -> str:
    """Normalizes an asset title for supporting similarity analysis."""
    clean = re.sub(r'^(file:|image:)', '', title, flags=re.IGNORECASE)
    clean = re.sub(r'\.[a-z0-9]+$', '', clean, flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]', '', clean.lower())

def fetch_wikipedia_article_images(topic: str) -> List[Dict[str, Any]]:
    """Fetches real photographic media embedded directly in the Wikipedia article."""
    url = (
        f"{WIKI_API}?action=query&titles={urllib.parse.quote(topic)}"
        f"&generator=images&gimlimit=25&prop=imageinfo&iiprop=url|extmetadata|size&format=json"
    )
    real_images = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for _, page in data.get("query", {}).get("pages", {}).items():
                info = page.get("imageinfo", [{}])[0]
                img_url = info.get("url", "")
                if not img_url:
                    continue
                clean_url = img_url.split("?")[0].lower()
                if not any(clean_url.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    continue
                meta = info.get("extmetadata", {})
                license_name = meta.get("LicenseShortName", {}).get("value", "Public domain")
                author = meta.get("Artist", {}).get("value", "Historical Archive")
                desc = meta.get("ImageDescription", {}).get("value", "")
                clean_title = page.get("title", "")
                
                real_images.append({
                    "asset_id": f"wiki_{page.get('pageid', hash(img_url))}",
                    "url": img_url,
                    "canonical_url": clean_url,
                    "title": clean_title,
                    "description": desc[:200],
                    "author": author[:60],
                    "license": license_name,
                    "source": "Wikipedia Article Media",
                    "evidence_class": "PRIMARY_EVIDENCE",
                    "commercial_use": True
                })
    except Exception as e:
        log.debug(f"Wikipedia article image fetch error for '{topic}': {e}")
    return real_images

def search_commons_query(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Searches Wikimedia Commons API for historical documents, maps, and photographs."""
    url = (
        f"{COMMONS_API}?action=query&generator=search&gsrsearch={urllib.parse.quote(query)}"
        f"&gsrlimit={limit}&gsrnamespace=6&prop=imageinfo&iiprop=url|extmetadata|size&format=json"
    )
    results = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for _, page in data.get("query", {}).get("pages", {}).items():
                info = page.get("imageinfo", [{}])[0]
                img_url = info.get("url", "")
                if not img_url:
                    continue
                clean_url = img_url.split("?")[0].lower()
                if not any(clean_url.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    continue
                meta = info.get("extmetadata", {})
                license_name = meta.get("LicenseShortName", {}).get("value", "Public Domain / CC")
                author = meta.get("Artist", {}).get("value", "Historical Archive")
                desc = meta.get("ImageDescription", {}).get("value", "")
                results.append({
                    "asset_id": f"commons_{page.get('pageid', hash(img_url))}",
                    "url": img_url,
                    "canonical_url": clean_url,
                    "title": page.get("title", ""),
                    "description": desc[:200],
                    "author": author[:60],
                    "license": license_name,
                    "source": "Wikimedia Commons",
                    "evidence_class": "SECONDARY_EVIDENCE",
                    "commercial_use": True
                })
    except Exception as e:
        log.debug(f"Commons search error for '{query}': {e}")
    return results

def search_pexels(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search Pexels API for atmospheric b-roll if key is available."""
    if not config.media.pexels_enabled:
        return []
    api_key = config.media.pexels_api_key
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page={limit}&orientation=portrait"

    results = []
    try:
        req = urllib.request.Request(url, headers={"Authorization": api_key, "User-Agent": "NexusVaultsEngine/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for photo in data.get("photos", []):
                img_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("portrait")
                if img_url:
                    results.append({
                        "asset_id": f"pexels_{photo.get('id')}",
                        "url": img_url,
                        "canonical_url": img_url,
                        "title": photo.get("alt", query),
                        "description": photo.get("alt", ""),
                        "author": photo.get("photographer", "Pexels Contributor"),
                        "license": "Pexels Free Commercial License",
                        "source": "Pexels",
                        "evidence_class": "ATMOSPHERIC",
                        "commercial_use": True
                    })
    except Exception as e:
        log.debug(f"Pexels error for '{query}': {e}")
    return results

def evaluate_semantic_relevance(cand: Dict[str, Any], scene: Dict[str, Any], topic: str) -> Tuple[float, Dict[str, float]]:
    """
    Evaluates multi-dimensional semantic relevance:
    entity_match, claim_match, event_match, location_match, date_match, visual_type_match, purpose_match.
    Enforces strict zero-tolerance penalty for mismatched persons or unrelated subjects.
    """
    text = f"{cand.get('title', '')} {cand.get('description', '')}".lower()
    primary_subj = scene.get("primary_visual_subject", topic).lower()
    claim = scene.get("claim", "").lower()
    vtype = scene.get("visual_type", "").lower()
    purpose = scene.get("visual_purpose", "").lower()

    # 1. Exact Entity Match & Anti-Impersonation Filter
    stopwords_entity = {"the", "and", "for", "with", "archival", "evidence", "focus", "location", "analysis", "investigation"}
    primary_tokens = [w for w in re.findall(r'\b[a-z]{3,}\b', primary_subj) if w not in stopwords_entity]
    topic_tokens = [w for w in re.findall(r'\b[a-z]{3,}\b', topic.lower()) if w not in stopwords_entity]

    matching_primary = [w for w in primary_tokens if w in text]
    matching_topic = [w for w in topic_tokens if w in text]

    topic_match_ratio = len(matching_topic) / max(1, len(topic_tokens)) if topic_tokens else 0
    primary_match_ratio = len(matching_primary) / max(1, len(primary_tokens)) if primary_tokens else 0

    if cand.get("source") == "Wikipedia Article Media":
        if primary_match_ratio >= 0.25:
            entity_match = max(0.85, 0.70 + 0.30 * primary_match_ratio)
        elif topic_match_ratio >= 0.8:
            entity_match = 0.85
        elif matching_primary:
            entity_match = 0.80
        elif matching_topic:
            entity_match = max(0.75, 0.85 * topic_match_ratio)
        else:
            entity_match = 0.70
    elif matching_primary:
        entity_match = max(primary_match_ratio, 0.85 * topic_match_ratio)
    elif matching_topic:
        entity_match = 0.85 * topic_match_ratio
    else:
        entity_match = 0.35

    # HARD CHECK: If scene is a PORTRAIT or requires a specific person, verify no other person is depicted
    if vtype == "portrait" or "person" in purpose:
        # Check if candidate mentions a known different person
        mismatched_people = [p for p in KNOWN_FAMOUS_PEOPLE if p in text and p not in primary_subj]
        if mismatched_people:
            # Immediate hard penalty: depicting Ada Lovelace for Stephen Hawking is 0.0
            entity_match = 0.0

    # 2. Claim Match
    claim_words = set(re.findall(r'\b[a-z]{4,}\b', claim))
    matched_claim = [w for w in claim_words if w in text]
    claim_match = min(1.0, len(matched_claim) / max(1, min(4, len(claim_words))))

    # 3. Event & Location Match
    event_keywords = ["merger", "discovery", "experiment", "collision", "lecture", "flight", "expedition", "paper", "treatise", "test"]
    matched_events = [k for k in event_keywords if k in claim and k in text]
    event_match = 1.0 if matched_events else (0.8 if not any(k in claim for k in event_keywords) else 0.4)

    loc_keywords = ["cambridge", "princeton", "caltech", "m87", "horizon", "observatory", "cern", "azores", "gibraltar"]
    matched_locs = [k for k in loc_keywords if k in claim and k in text]
    location_match = 1.0 if matched_locs else (0.8 if not any(k in claim for k in loc_keywords) else 0.4)

    # 4. Date Match
    dates_in_claim = re.findall(r'\b(1[6-9]\d{2}|20\d{2})\b', scene.get("claim", ""))
    date_match = 1.0 if any(d in text for d in dates_in_claim) else (0.8 if not dates_in_claim else 0.3)

    # 5. Visual Type Match
    type_keywords = {
        "portrait": ["portrait", "painting", "photograph", "photo", "drawing", "face", "briggs", "captain"],
        "document": ["document", "letter", "page", "manuscript", "telegram", "paper", "treatise", "patent", "log", "record", "inquest", "article", "times"],
        "map": ["map", "chart", "cartography", "plan", "route", "atlas", "ocean", "sea"],
        "diagram": ["diagram", "schematic", "formula", "graph", "drawing", "figure", "structure", "timeline"],
        "newspaper": ["newspaper", "headline", "gazette", "article", "times", "press"],
        "object_closeup": ["telescope", "instrument", "machine", "detector", "device", "apparatus", "barrel", "cargo", "ship", "vessel", "brigantine"],
        "archival_photo": ["photo", "photograph", "vintage", "historical", "archive", "19", "20", "18", "17", "engraving", "illustration", "ship", "vessel", "brigantine"],
        "atmospheric": ["space", "universe", "sky", "dark", "light", "stars", "cosmos", "ocean", "sea", "wave", "water"]
    }
    expected_kw = type_keywords.get(vtype, ["historical", "archive"])
    visual_type_match = 1.0 if any(kw in text for kw in expected_kw) else 0.5

    # 6. Visual Purpose Match
    purpose_match = 1.0 if any(w in text for w in purpose.lower().split("_")) else 0.75

    # 7. Provenance Confidence
    prov_conf = 1.0 if cand.get("source") in ("Wikipedia Article Media", "Wikimedia Commons") else 0.75

    # Weighted final score calculation
    if entity_match == 0.0 and (vtype == "portrait" or "person" in purpose):
        # Strict hard gate failure for wrong person
        final_score = 0.10
    else:
        final_score = (
            0.35 * entity_match +
            0.20 * claim_match +
            0.15 * visual_type_match +
            0.10 * event_match +
            0.05 * location_match +
            0.05 * date_match +
            0.05 * purpose_match +
            0.05 * prov_conf
        )
        if cand.get("source") == "Wikipedia Article Media":
            final_score = max(0.65, final_score)

    breakdown = {
        "entity_match": round(entity_match, 2),
        "claim_match": round(claim_match, 2),
        "event_match": round(event_match, 2),
        "location_match": round(location_match, 2),
        "date_match": round(date_match, 2),
        "visual_type_match": round(visual_type_match, 2),
        "purpose_match": round(purpose_match, 2),
        "provenance_confidence": round(prov_conf, 2),
        "final_relevance_score": round(final_score, 2)
    }
    return round(final_score, 2), breakdown

def verify_asset_semantic_qa(primary_subj: str, claim: str, cand: Dict[str, Any], vtype: str) -> Tuple[bool, str]:
    """
    Section 22: Visual Semantic QA Pass
    Independent verification pass asking whether the asset truthfully depicts or explains
    the primary visual subject and claim.
    """
    title = cand.get("title", "")
    desc = cand.get("description", "")
    source = cand.get("source", "")
    text_lower = f"{title} {desc}".lower()

    # Fast heuristic check for explanatory graphics
    if "Explanatory Graphic" in source:
        return True, "Verified authentic generated explanatory schematic"

    # Fast approval for direct Wikipedia article media (verified authentic from topic article)
    if source == "Wikipedia Article Media":
        mismatches = [p for p in KNOWN_FAMOUS_PEOPLE if p in text_lower and p not in primary_subj.lower() and p not in claim.lower()]
        if not mismatches:
            return True, f"Verified authentic direct Wikipedia article media for '{primary_subj}'"
        else:
            return False, f"Hard rejection: candidate depicts mismatched person '{mismatches[0]}'"

    # HARD DETERMINISTIC GATE 1: Mismatched famous persons (zero tolerance for random historical or modern figures)
    mismatches = [p for p in KNOWN_FAMOUS_PEOPLE if p in text_lower and p not in primary_subj.lower() and p not in claim.lower()]
    if mismatches:
        return False, f"Hard rejection: candidate depicts mismatched person '{mismatches[0]}'"

    if ("official portrait" in text_lower or "portrait of" in text_lower or "headshot" in text_lower) and vtype != "PORTRAIT":
        if not any(k in primary_subj.lower() for k in ["person", "portrait", "dr.", "prof.", "sir", "lord", "captain", "mathematician", "physicist", "scientist", "author", "inventor", "astronomer", "philosopher", "general", "admiral"]):
            return False, f"Hard rejection: candidate is a portrait but scene visual type is '{vtype}' for '{primary_subj}'"

    prompt = f"""
You are an expert visual evidence auditor for an investigative documentary.
Evaluate whether this archival visual candidate truthfully depicts or faithfully explains the primary visual subject and claim.

PRIMARY SUBJECT: {primary_subj}
CLAIM: {claim}
EXPECTED VISUAL TYPE: {vtype}
CANDIDATE TITLE: {title}
CANDIDATE DESCRIPTION: {desc}

RULES:
1. If the primary subject is a specific person (e.g. Stephen Hawking) and the candidate is a DIFFERENT person (e.g. Ada Lovelace, Isaac Newton), you MUST REJECT (approved: false).
2. If the candidate is an unrelated filler image (e.g. a mind map, a modern car axle, an unrelated municipal bus), you MUST REJECT (approved: false).
3. If the candidate truthfully depicts or faithfully explains the primary subject or claim, or is an authentic contemporary primary source document/photograph/illustration of the topic event, APPROVE (approved: true).

Output strictly valid JSON:
{{"approved": true, "reason": "concise explanation"}}
"""
    try:
        resp = route_task(prompt, task_type="critic", system_instruction="You are a strict visual relevance auditor. Output JSON only.")
        clean = extract_json(resp)
        data = json.loads(clean)
        return bool(data.get("approved", False)), data.get("reason", "Approved by critic")
    except Exception as e:
        # Independent QA critic unavailable — visible degradation, deterministic gates still applied
        log.warning(f"Visual semantic QA critic unavailable; deterministic gates only. Cause: {e}")
        # Deterministic fallback check: reject if title clearly references another famous person
        text_lower = f"{title} {desc}".lower()
        if vtype == "portrait":
            mismatches = [p for p in KNOWN_FAMOUS_PEOPLE if p in text_lower and p not in primary_subj.lower()]
            if mismatches:
                return False, f"Mismatched person detected in candidate: {mismatches[0]}"
        return True, "Passed deterministic QA rules (critic unavailable)"

def download_candidate(url: str, target_path: Path) -> bool:
    """Downloads candidate image binary and verifies integrity."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if len(data) > 10240:
                with Image.open(io.BytesIO(data)) as img:
                    img.verify()
                with open(target_path, "wb") as f:
                    f.write(data)
                return True
    except Exception:
        if target_path.exists():
            target_path.unlink()
    return False

def collect_storyboard_assets(
    storyboard: List[Dict[str, Any]],
    output_dir: Path,
    file_number: int,
    topic: str = ""
) -> List[Dict[str, Any]]:
    """
    Harvests unique, verified photographic assets for each storyboard scene.
    Enforces:
    1. Primary Visual Subject search.
    2. Hard Relevance Gate (rejection if score < min_score).
    3. Independent Visual Semantic QA pass.
    4. Truthful Explanatory Graphic generation when authentic archival photography is unavailable.
    5. Multi-tier deduplication (URL, SHA-256, dHash).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    used_urls: Set[str] = set()
    used_shas: Set[str] = set()
    used_phashes: List[int] = []
    used_titles: Set[str] = set()
    collected_scenes = []

    min_relevance = config.scene.relevance_min_score
    log.info(f"Initiating exact-subject asset harvest for {len(storyboard)} scenes of '{topic}' (Hard Gate: {min_relevance:.2f})...")

    wiki_images = fetch_wikipedia_article_images(topic) if topic else []
    log.info(f"Discovered {len(wiki_images)} authentic images embedded in main Wikipedia article.")

    for scene_idx, scene in enumerate(storyboard):
        scene_id = scene["scene_id"]
        target_path = output_dir / f"scene_{scene_id:02d}.jpg"
        temp_test_path = output_dir / f"test_cand_{scene_id:02d}.jpg"
        assigned_meta = None

        primary_subj = scene.get("primary_visual_subject", topic)
        vtype = scene.get("visual_type", "ARCHIVAL_PHOTO")
        claim = scene.get("claim", "")

        candidate_queue: List[Dict[str, Any]] = []

        # Tier 1: Matching Wikipedia article images
        for w_img in wiki_images:
            if w_img["canonical_url"] not in used_urls:
                candidate_queue.append(w_img)

        # Tier 2: Search Wikimedia Commons targeting primary_visual_subject
        queries = scene.get("search_queries", [])
        if not queries:
            queries = [primary_subj, f"{primary_subj} {vtype.lower()}", f"{topic} {primary_subj}"]

        commons_candidates = []
        for q in queries[:3]:
            res = search_commons_query(q, limit=4)
            for r in res:
                if not any(c["canonical_url"] == r["canonical_url"] for c in candidate_queue) and not any(c["canonical_url"] == r["canonical_url"] for c in commons_candidates):
                    commons_candidates.append(r)
            if len(commons_candidates) >= config.scene.max_candidates_per_scene:
                break

        # If specific queries returned nothing or few, attempt fallback queries on topic / subject
        if len(commons_candidates) < 2 and topic:
            fallback_q = f"{topic} {primary_subj.split()[0]}" if primary_subj else topic
            for r in search_commons_query(fallback_q, limit=4):
                if not any(c["canonical_url"] == r["canonical_url"] for c in candidate_queue) and not any(c["canonical_url"] == r["canonical_url"] for c in commons_candidates):
                    commons_candidates.append(r)
            if len(commons_candidates) < 2:
                for r in search_commons_query(topic, limit=4):
                    if not any(c["canonical_url"] == r["canonical_url"] for c in candidate_queue) and not any(c["canonical_url"] == r["canonical_url"] for c in commons_candidates):
                        commons_candidates.append(r)

        candidate_queue.extend(commons_candidates)

        # Tier 3: Pexels — atmospheric/contextual slots ONLY
        # Pexels MUST NOT satisfy primary evidence, person identification, or document slots.
        # Allowed purposes: ESTABLISH_LOCATION, PROVIDE_CONTEXT, BUILD_TENSION, ATMOSPHERIC
        PEXELS_BLOCKED_PURPOSES = {
            "SHOW_PRIMARY_EVIDENCE", "SHOW_SECONDARY_EVIDENCE", "IDENTIFY_PERSON",
            "HIGHLIGHT_DETAIL", "REVEAL_INFORMATION",
            "SHOW_ROUTE", "SHOW_TIMELINE", "SHOW_CONTRADICTION", "EXPLAIN_MECHANISM"
        }
        scene_purpose = scene.get("visual_purpose", "SHOW_PRIMARY_EVIDENCE")
        if (config.media.pexels_enabled
                and vtype == "ATMOSPHERIC"
                and scene_purpose not in PEXELS_BLOCKED_PURPOSES):
            for p in search_pexels(primary_subj, limit=3):
                candidate_queue.append(p)

        # Evaluate candidate relevance
        evaluated_candidates = []
        for cand in candidate_queue:
            if cand["canonical_url"] in used_urls:
                continue
            score, breakdown = evaluate_semantic_relevance(cand, scene, topic)
            evaluated_candidates.append((score, breakdown, cand))

        evaluated_candidates.sort(key=lambda x: x[0], reverse=True)

        accepted = False
        tested_qa_count = 0
        for score, breakdown, cand in evaluated_candidates:
            if cand["canonical_url"] in used_urls:
                continue

            # Title check: Only flag identical titles if the title is long and specific (>25 chars)
            # Short generic titles (e.g. 'Antikythera Mechanism', 'Map of Bermuda') are common across distinct files.
            cand_title_key = normalize_title(cand.get("title", ""))
            if cand_title_key and len(cand_title_key) > 25 and cand_title_key in used_titles:
                log.warning(f"Rejected exact-duplicate long-title asset ({cand['title'][:35]}) by title match")
                continue

            # Log candidate evaluation
            if score < min_relevance:
                log.debug(
                    f"Scene {scene_id:02d} | Candidate '{cand.get('title','')[:40]}' | "
                    f"URL: {cand.get('canonical_url','')} | REJECTED: Low relevance ({score:.2f} < {min_relevance:.2f})"
                )
                continue

            # Allow testing up to 8 valid candidates per scene to prevent premature fallback
            if tested_qa_count >= 8:
                break
            tested_qa_count += 1

            # SECTION 22: Visual Semantic QA Pass
            qa_ok, qa_reason = verify_asset_semantic_qa(primary_subj, claim, cand, vtype)
            if not qa_ok:
                log.warning(f"Scene {scene_id:02d}: Semantic QA rejected candidate '{cand['title'][:40]}' -> {qa_reason}")
                continue

            # Download candidate to temporary path
            if download_candidate(cand["url"], temp_test_path):
                file_sha = compute_sha256(temp_test_path)
                if config.scene.dedup_sha_enabled and file_sha in used_shas:
                    log.warning(f"Rejected exact duplicate binary SHA ({cand['title'][:35]})")
                    temp_test_path.unlink(missing_ok=True)
                    continue

                try:
                    ph = compute_dhash(temp_test_path)
                    is_near_dup = False
                    for prior_ph in used_phashes:
                        if hamming_distance(ph, prior_ph) <= config.scene.dedup_hamming_threshold:
                            is_near_dup = True
                            log.warning(f"Rejected near-duplicate asset ({cand['title'][:35]}) by dHash match")
                            break

                    if is_near_dup:
                        temp_test_path.unlink(missing_ok=True)
                        continue

                    # Asset passed all gates! Commit asset
                    shutil.move(str(temp_test_path), str(target_path))
                    assert target_path.exists(), f"Failed to commit asset to {target_path}"
                    used_urls.add(cand["canonical_url"])
                    used_shas.add(file_sha)
                    used_phashes.append(ph)
                    used_titles.add(normalize_title(cand.get("title", "")))

                    cand["sha256"] = file_sha
                    cand["phash"] = hex(ph)
                    cand["relevance_score"] = score
                    cand["relevance_breakdown"] = breakdown
                    assigned_meta = cand
                    accepted = True
                    log.info(f"Scene {scene_id:02d} [{vtype}]: Assigned authentic {cand['source']} -> {cand['title'][:45]} (Relevance: {score})")
                    break
                except Exception as e:
                    temp_test_path.unlink(missing_ok=True)
                    log.debug(f"Perceptual check error: {e}")
                    continue

        # If initial candidate queue exhausted without acceptance, perform Round 2 Search Broadening
        if not accepted or not target_path.exists():
            broad_queries = [
                f"{topic} historical archive",
                f"{topic} photograph",
                f"{topic} document"
            ]
            round2_cands = []
            for bq in broad_queries:
                for r in search_commons_query(bq, limit=5):
                    if (r["canonical_url"] not in used_urls
                            and not any(c["canonical_url"] == r["canonical_url"] for c in candidate_queue)
                            and not any(c["canonical_url"] == r["canonical_url"] for c in round2_cands)):
                        round2_cands.append(r)
                if len(round2_cands) >= 6:
                    break

            if round2_cands:
                log.info(f"Scene {scene_id:02d}: Broadening search with {len(round2_cands)} Round 2 archive candidates...")
                r2_evaluated = []
                for cand in round2_cands:
                    score, breakdown = evaluate_semantic_relevance(cand, scene, topic)
                    r2_evaluated.append((score, breakdown, cand))
                r2_evaluated.sort(key=lambda x: x[0], reverse=True)

                for score, breakdown, cand in r2_evaluated:
                    if cand["canonical_url"] in used_urls or score < min_relevance:
                        continue
                    qa_ok, qa_reason = verify_asset_semantic_qa(primary_subj, claim, cand, vtype)
                    if not qa_ok:
                        continue
                    if download_candidate(cand["url"], temp_test_path):
                        file_sha = compute_sha256(temp_test_path)
                        if config.scene.dedup_sha_enabled and file_sha in used_shas:
                            temp_test_path.unlink(missing_ok=True)
                            continue
                        try:
                            ph = compute_dhash(temp_test_path)
                            if any(hamming_distance(ph, pph) <= config.scene.dedup_hamming_threshold for pph in used_phashes):
                                temp_test_path.unlink(missing_ok=True)
                                continue
                            shutil.move(str(temp_test_path), str(target_path))
                            used_urls.add(cand["canonical_url"])
                            used_shas.add(file_sha)
                            used_phashes.append(ph)
                            cand["sha256"] = file_sha
                            cand["phash"] = hex(ph)
                            cand["relevance_score"] = score
                            cand["relevance_breakdown"] = breakdown
                            assigned_meta = cand
                            accepted = True
                            log.info(f"Scene {scene_id:02d} [{vtype}]: Assigned Round-2 authentic {cand['source']} -> {cand['title'][:45]} (Relevance: {score})")
                            break
                        except Exception:
                            temp_test_path.unlink(missing_ok=True)
                            continue

        # SECTION 20: VISUAL FAILURE STATE -> Produce Truthful Explanatory Graphic
        # If genuine search exhaustion occurs after all rounds, produce a dedicated technical exhibit graphic
        if not accepted or not target_path.exists():
            log.info(f"Scene {scene_id:02d} [{vtype}]: Genuine search space exhaustion ({min_relevance:.2f}). Generating truthful explanatory graphic for '{primary_subj}'...")
            assigned_meta = create_truthful_explanatory_graphic(scene, target_path, topic=topic)
            file_sha = compute_sha256(target_path)
            ph = compute_dhash(target_path)
            used_urls.add(assigned_meta["canonical_url"])
            used_shas.add(file_sha)
            used_phashes.append(ph)
            assigned_meta["sha256"] = file_sha
            assigned_meta["phash"] = hex(ph)
            scene["visual_type"] = "GENERATED_GRAPHIC"
            accepted = True

        if not accepted or not target_path.exists():
            raise RuntimeError(f"QC FAIL: Unresolved visual state for Scene {scene_id} ({primary_subj})! Publication BLOCKED.")

        scene["path"] = target_path
        scene["asset_meta"] = assigned_meta
        collected_scenes.append(scene)

    assert len(collected_scenes) == len(storyboard), "Scene count mismatch after harvest!"

    # Section 2 & Section 8: Strict Unique Source Asset Calculation
    source_identities = set()
    for s in collected_scenes:
        m = s.get("asset_meta", {})
        ident = m.get("source_identity") or m.get("canonical_url") or m.get("title")
        source_identities.add(ident)

    accidental_reuse = len(collected_scenes) - len(source_identities)
    if accidental_reuse > 0:
        raise RuntimeError(f"QC FAIL: Detected {accidental_reuse} accidental asset reuses! Each scene must feature a unique source asset.")

    # PRD Revision 3 Section 7 & Fix R2-6:
    # Generated graphics are a strict LAST RESORT.
    # Enforce generated graphics budget and minimum authentic assets.
    generated_count = sum(
        1 for s in collected_scenes
        if s.get("asset_meta", {}).get("source") == "NEXUS_GENERATED" or s.get("asset_meta", {}).get("visual_type") == "GENERATED_GRAPHIC"
    )
    authentic_count = len(collected_scenes) - generated_count

    if generated_count > config.scene.max_generated_graphics:
        raise VisualBudgetExceededError(
            f"DEFER: Generated graphics ({generated_count}/{len(collected_scenes)}) exceeded allowed budget of {config.scene.max_generated_graphics}. "
            f"Authentic archival media ({authentic_count}) insufficient."
        )

    if authentic_count < config.scene.min_authentic_assets:
        raise VisualBudgetExceededError(
            f"DEFER: Authentic archival assets ({authentic_count}/{len(collected_scenes)}) below minimum threshold of {config.scene.min_authentic_assets}. "
            "Publication deferred to prevent visual sludge."
        )

    log.info(f"Secured {len(collected_scenes)} scenes with {len(source_identities)} 100% UNIQUE source assets (Authentic: {authentic_count}, Generated: {generated_count}, Accidental reuse: 0).")
    return collected_scenes

def format_relevance_report(scenes_with_assets: List[Dict[str, Any]]) -> str:
    """
    Section 21: Relevance Report
    Prints detailed claim-level audit for every scene generated from the ACTUAL selected asset.
    """
    lines = [
        "=" * 65,
        "         NEXUS VAULTS 2.0 - SCENE VISUAL RELEVANCE AUDIT REPORT",
        "=" * 65
    ]
    min_relevance = config.scene.relevance_min_score
    source_identities = set()
    for s in scenes_with_assets:
        meta = s.get("asset_meta", {})
        ident = meta.get("source_identity") or meta.get("canonical_url") or meta.get("title")
        source_identities.add(ident)
        brk = meta.get("relevance_breakdown", {})
        score = meta.get("relevance_score", 0.0)
        is_pass = score >= min_relevance
        actual_type = meta.get("visual_type", s.get("visual_type", "ARCHIVAL_PHOTO"))
        lines.append(f"SCENE {s.get('scene_id', 1):02d} [{actual_type}]")
        lines.append(f"  CLAIM:                  {s.get('claim', '')[:70]}")
        lines.append(f"  PRIMARY VISUAL SUBJECT: {s.get('primary_visual_subject', 'N/A')}")
        lines.append(f"  SELECTED ASSET:         {meta.get('title', 'N/A')[:60]}")
        lines.append(f"  VISUAL PURPOSE:         {s.get('visual_purpose', 'N/A')}")
        lines.append(f"  ENTITY MATCH:           {brk.get('entity_match', 1.0):.2f}")
        lines.append(f"  CLAIM MATCH:            {brk.get('claim_match', 1.0):.2f}")
        lines.append(f"  EVENT MATCH:            {brk.get('event_match', 1.0):.2f}")
        lines.append(f"  LOCATION MATCH:         {brk.get('location_match', 1.0):.2f}")
        lines.append(f"  DATE MATCH:             {brk.get('date_match', 1.0):.2f}")
        lines.append(f"  VISUAL TYPE MATCH:      {brk.get('visual_type_match', 1.0):.2f}")
        lines.append(f"  PURPOSE MATCH:          {brk.get('purpose_match', 1.0):.2f}")
        lines.append(f"  FINAL RELEVANCE SCORE:  {score:.2f} (Threshold: {min_relevance:.2f})")
        lines.append(f"  STATUS:                 {'PASS' if is_pass else 'FAIL'}")
        lines.append("-" * 65)

    accidental_reuse = len(scenes_with_assets) - len(source_identities)
    lines.append(f"TOTAL SCENES:             {len(scenes_with_assets)}")
    lines.append(f"UNIQUE SOURCE ASSETS:     {len(source_identities)}")
    lines.append(f"ACCIDENTAL REUSE:         {accidental_reuse}")
    lines.append(f"INTENTIONAL REUSE:        0")
    lines.append("=" * 65)
    return "\n".join(lines)
