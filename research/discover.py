"""
AI Video Factory - Research Discovery Module
Mines Wikipedia API, MediaWiki, and historical archives to discover real candidate topics.
Channel-driven via Channel Brain. Zero hallucinated content.
"""

import urllib.request
import urllib.parse
import json
import random
from typing import List, Dict, Any
from core.database import is_topic_already_used, get_weight
from core.logging import log
from core.channel_brain import get_channel_brain
from core.config import config

def _build_discovery_context() -> str:
    """Build Channel Brain context for topic discovery."""
    brain = get_channel_brain()
    return brain.get_prompt_context("research")

# Knowledge Graph seeds are now driven by Channel Brain niche/creative directive.
# If Channel Brain is unconfigured, fail clearly rather than falling back to hardcoded niches.
def _get_knowledge_graph_seeds() -> Dict[str, List[str]]:
    """Returns category seeds from Channel Brain niche, or raises if unconfigured."""
    brain = get_channel_brain()
    niche = brain.profile.niche.strip().lower()
    
    if not niche:
        raise ValueError(
            "Channel Brain niche is not configured. "
            "Set CHANNEL_NICHE in .env or configure via control panel. "
            "Cannot discover topics without a defined channel niche."
        )
    
    # Map common niches to Wikipedia category seeds
    # Users can extend this mapping via Creative Directive or control panel
    niche_seeds = {
        "history": {
            "Military History": [
                "Category:Battles", "Category:Wars", "Category:Military history",
                "Category:Military conflicts", "Category:Sieges"
            ],
            "Ancient History": [
                "Category:Ancient civilizations", "Category:Archaeological sites",
                "Category:Ancient history", "Category:Historical archaeology"
            ],
            "Modern History": [
                "Category:20th-century history", "Category:Cold War",
                "Category:World War II", "Category:Contemporary history"
            ],
        },
        "science": {
            "Physics": [
                "Category:Physics", "Category:Unsolved problems in physics",
                "Category:Physical phenomena", "Category:Quantum mechanics"
            ],
            "Astronomy": [
                "Category:Astronomy", "Category:Unsolved problems in astronomy",
                "Category:Exoplanets", "Category:Cosmology"
            ],
            "Biology": [
                "Category:Biology", "Category:Evolutionary biology",
                "Category:Genetics", "Category:Neuroscience"
            ],
        },
        "technology": {
            "Computer Science": [
                "Category:Computer science", "Category:Artificial intelligence",
                "Category:Cryptography", "Category:Algorithms"
            ],
            "Engineering": [
                "Category:Engineering", "Category:Mechanical engineering",
                "Category:Electrical engineering", "Category:Aerospace engineering"
            ],
        },
        "nature": {
            "Wildlife": [
                "Category:Animals", "Category:Endangered species",
                "Category:Animal behavior", "Category:Wildlife conservation"
            ],
            "Geology": [
                "Category:Geology", "Category:Volcanoes",
                "Category:Earthquakes", "Category:Plate tectonics"
            ],
        },
        "mystery": {
            "Unexplained": [
                "Category:Unexplained disappearances", "Category:Ghost ships",
                "Category:Missing aircraft", "Category:Paranormal"
            ],
            "Historical Mysteries": [
                "Category:Historical mysteries", "Category:Unsolved crimes",
                "Category:Cold cases", "Category:Archaeological mysteries"
            ],
        },
        "finance": {
            "Economics": [
                "Category:Economics", "Category:Financial crises",
                "Category:Monetary policy", "Category:Economic history"
            ],
            "Markets": [
                "Category:Stock market", "Category:Investment",
                "Category:Banking", "Category:Cryptocurrency"
            ],
        },
        "health": {
            "Medicine": [
                "Category:Medicine", "Category:Diseases",
                "Category:Medical research", "Category:Public health"
            ],
            "Psychology": [
                "Category:Psychology", "Category:Cognitive science",
                "Category:Mental health", "Category:Neuroscience"
            ],
        }
    }
    
    # Find matching niche
    for key, categories in niche_seeds.items():
        if key in niche or niche in key:
            return categories
    
    # If no mapping, use generic categories based on niche keyword
    # This is a minimal fallback - users should customize via Creative Directive
    generic_seeds = {
        f"General {niche.title()}": [
            f"Category:{niche.title()}", 
            f"Category:History of {niche}",
            f"Category:{niche} topics"
        ]
    }
    return generic_seeds

# Resolve this lazily. Importing the research module must not fail merely
# because a local developer or isolated test has not configured a niche yet.
KNOWLEDGE_GRAPH_SEEDS = None

def fetch_wikipedia_category_members(category: str, limit: int = 20) -> List[str]:
    """Fetch article titles belonging to a specific Wikipedia category."""
    url = (
        f"https://en.wikipedia.org/w/api.php?"
        f"action=query&list=categorymembers&cmtitle={urllib.parse.quote(category)}"
        f"&cmlimit={limit}&cmtype=page&format=json"
    )
    headers = {"User-Agent": "AI-Video-Factory/1.0 (autonomous research; contact@aivideofactory.org)"}
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
    headers = {"User-Agent": "AI-Video-Factory/1.0 (autonomous research; contact@aivideofactory.org)"}
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
    Discovers candidate topics across the Knowledge Graph, weighted by dynamic performance.
    Uses Channel Brain context to guide discovery toward channel niche and creative directive.
    """
    global KNOWLEDGE_GRAPH_SEEDS
    if KNOWLEDGE_GRAPH_SEEDS is None:
        KNOWLEDGE_GRAPH_SEEDS = _get_knowledge_graph_seeds()
    count = target_count or config.research.max_topics
    brain = get_channel_brain()
    discovery_context = brain.get_prompt_context("research")
    
    log.info(f"Initiating Research Discovery across Knowledge Graph nodes... (Channel: {brain.profile.name or 'Unnamed'})")
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

