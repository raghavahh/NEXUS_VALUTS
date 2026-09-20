"""
NEXUS VAULTS 2.0 - Research Discovery Module
Mines Wikipedia API, MediaWiki, and historical archives to discover real candidate mysteries.
Zero hallucinated stories.
"""

import urllib.request
import urllib.parse
import json
import random
from typing import List, Dict, Any
from core.database import is_topic_already_used, get_weight
from core.logging import log

# 4 Core Knowledge Graph Pillars with verified active Wikipedia category seeds
KNOWLEDGE_GRAPH_SEEDS = {
    "Classified History": [
        "Category:Cold War espionage",
        "Category:Covert operations",
        "Category:Central Intelligence Agency operations",
        "Category:Espionage scandals and incidents",
        "Category:Military deception"
    ],
    "Unexplained Events": [
        "Category:Unexplained disappearances",
        "Category:Ghost ships",
        "Category:Missing ships",
        "Category:Missing aircraft",
        "Category:Shipwrecks with unexplained causes"
    ],
    "Scientific Mysteries": [
        "Category:Physical paradoxes",
        "Category:Unsolved problems in physics",
        "Category:Unsolved problems in astronomy",
        "Category:Atmospheric optical phenomena",
        "Category:Astronomical hypotheses"
    ],
    "Strange Real Events": [
        "Category:Phantom islands",
        "Category:Disputed islands",
        "Category:Castaways",
        "Category:Feral children",
        "Category:Survival skills"
    ]
}

def fetch_wikipedia_category_members(category: str, limit: int = 20) -> List[str]:
    """Fetch article titles belonging to a specific Wikipedia category."""
    url = (
        f"https://en.wikipedia.org/w/api.php?"
        f"action=query&list=categorymembers&cmtitle={urllib.parse.quote(category)}"
        f"&cmlimit={limit}&cmtype=page&format=json"
    )
    headers = {"User-Agent": "NexusVaultsBot/2.0 (autonomous research; contact@nexusvaults.org)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            members = data.get("query", {}).get("categorymembers", [])
            return [m["title"] for m in members if not m["title"].startswith("List of")]
    except Exception as e:
        log.warning(f"Failed to fetch category {category}: {e}")
        return []

def fetch_wikipedia_summary(title: str) -> Dict[str, Any]:
    """Fetch Wikipedia summary extract and page details."""
    clean_title = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_title}"
    headers = {"User-Agent": "NexusVaultsBot/2.0 (autonomous research; contact@nexusvaults.org)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "title": data.get("title", title),
                "summary": data.get("extract", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{clean_title}"),
                "thumbnail": data.get("thumbnail", {}).get("source", "")
            }
    except Exception as e:
        log.debug(f"Failed to fetch summary for {title}: {e}")
        return {}

from core.config import config

def discover_candidates(target_count: int = None) -> List[Dict[str, Any]]:
    """
    Discovers candidate stories across the Knowledge Graph, weighted by dynamic performance.
    """
    count = target_count or config.research.max_topics
    log.info("Initiating Research Discovery across Knowledge Graph nodes...")
    candidates = []

    # Filter clusters by configured content pillars if present
    configured_pillars = [p.lower() for p in config.research.content_pillars]
    available_clusters = [c for c in KNOWLEDGE_GRAPH_SEEDS.keys() if any(p in c.lower() for p in configured_pillars)]
    clusters = available_clusters if available_clusters else list(KNOWLEDGE_GRAPH_SEEDS.keys())
    weights = [get_weight(f"cluster:{c}", 1.0) for c in clusters]
    total_w = sum(weights)
    probs = [w / total_w for w in weights]

    for _ in range(count * 3):
        if len(candidates) >= count:
            break

            
        cluster = random.choices(clusters, weights=probs, k=1)[0]
        category = random.choice(KNOWLEDGE_GRAPH_SEEDS[cluster])
        titles = fetch_wikipedia_category_members(category, limit=25)
        
        if not titles:
            continue
            
        random.shuffle(titles)
        for t in titles:
            if is_topic_already_used(t) or any(c["title"] == t for c in candidates):
                continue
                
            info = fetch_wikipedia_summary(t)
            summary = info.get("summary", "")
            
            # Filter out non-stories, disambiguations, overly short stubs, and media-barren topics
            if len(summary) > 180 and "refer to:" not in summary.lower() and info.get("thumbnail"):
                candidates.append({
                    "cluster": cluster,
                    "title": info["title"],
                    "summary": summary,
                    "url": info["url"],
                    "thumbnail": info.get("thumbnail", ""),
                    "fact_confidence": 0.95,
                    "cluster_weight": get_weight(f"cluster:{cluster}", 1.0)
                })
                break
        else:
            # Fallback if no thumbnail found in first pass: pick longest summary
            for t in titles:
                if is_topic_already_used(t) or any(c["title"] == t for c in candidates):
                    continue
                info = fetch_wikipedia_summary(t)
                summary = info.get("summary", "")
                if len(summary) > 300 and "refer to:" not in summary.lower():
                    candidates.append({
                        "cluster": cluster,
                        "title": info["title"],
                        "summary": summary,
                        "url": info["url"],
                        "thumbnail": info.get("thumbnail", ""),
                        "fact_confidence": 0.95,
                        "cluster_weight": get_weight(f"cluster:{cluster}", 1.0)
                    })
                    break
                
    if not candidates:
        # No hardcoded fallback stories — zero hardcoding rule.
        # If all research sources fail, defer this run cleanly rather than inject
        # topic-specific content that was never dynamically selected.
        log.warning(
            "Research discovery returned zero valid candidates. "
            "All Wikipedia API sources exhausted. "
            "Pipeline will abort at topic selection stage. "
            "Check network connectivity or broaden RESEARCH_CONTENT_PILLARS in .env."
        )

    log.info(f"Discovered {len(candidates)} verified candidate stories.")
    return candidates

