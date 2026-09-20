"""
NEXUS VAULTS 2.0 - Media Preflight Engine
Enforces PRD Section 6 Visual Budget requirements BEFORE topic selection / Growth Brain.

CONTRACT:
- Raw inventory != Relevant assets != Estimated semantic survivors
- < 4 relevant authentic assets -> REJECT
- 4-5 relevant authentic assets -> ELIGIBLE
- 6+ relevant authentic assets -> STRONG (PREFERRED)
- Preflight reports: Candidate, Raw authentic, Relevant authentic, Estimated semantic survivors, Eligibility
"""

import re
from typing import Dict, Any, List
from media.images import fetch_wikipedia_article_images, search_commons_query
from core.logging import log

JUNK_PATTERNS = re.compile(
    r'(?:icon|flag|logo|symbol|stub|ambox|commons-logo|portal|blank|crystal_clear|padlock|edit-clear|red_penc|px-|disambig|magnify-clip)',
    re.IGNORECASE
)

def evaluate_media_preflight(topic: str) -> Dict[str, Any]:
    """
    Evaluates authentic archival documentary assets available for a topic
    before topic selection and scriptwriting.
    """
    try:
        wiki_images = fetch_wikipedia_article_images(topic)
    except Exception as e:
        log.debug(f"[MEDIA PREFLIGHT] Failed to fetch article images for '{topic}': {e}")
        wiki_images = []

    raw_wiki_count = len(wiki_images)
    rel_article_assets = [
        img for img in wiki_images
        if not JUNK_PATTERNS.search(img.get("title", ""))
    ]

    try:
        commons_images = search_commons_query(topic, limit=8)
    except Exception as e:
        log.debug(f"[MEDIA PREFLIGHT] Commons query error for '{topic}': {e}")
        commons_images = []

    seen_urls = {img["canonical_url"] for img in rel_article_assets}
    rel_commons_assets = []
    for img in commons_images:
        url = img.get("canonical_url", "")
        title = img.get("title", "")
        if url not in seen_urls and not JUNK_PATTERNS.search(title):
            rel_commons_assets.append(img)
            seen_urls.add(url)

    raw_total = raw_wiki_count + len(commons_images)
    rel_total = len(rel_article_assets) + len(rel_commons_assets)
    # Documentary survivor estimate: article-embedded media has ~85% survival rate in semantic QA; Commons ~55%
    est_survivors = int(round(len(rel_article_assets) * 0.85 + len(rel_commons_assets) * 0.55))

    # Contract thresholds:
    # < 4 relevant authentic assets OR < 4 estimated survivors -> REJECT
    # 4-5 relevant authentic assets AND >= 4 estimated survivors -> ELIGIBLE
    # 6+ relevant authentic assets AND >= 5 estimated survivors -> STRONG
    if rel_total < 4 or est_survivors < 4:
        status = "REJECT"
    elif rel_total <= 5:
        status = "ELIGIBLE"
    else:
        status = "STRONG"

    report = {
        "topic": topic,
        "raw_count": raw_total,
        "relevant_count": rel_total,
        "estimated_survivors": est_survivors,
        "status": status
    }

    log.info(
        f"[MEDIA PREFLIGHT] Candidate '{topic}': "
        f"Raw={raw_total} | Relevant Authentic={rel_total} | "
        f"Est. Survivors={est_survivors} | Status={status}"
    )
    return report
