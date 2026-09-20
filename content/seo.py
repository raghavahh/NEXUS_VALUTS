"""
NEXUS VAULTS 2.0 - Documentary SEO & Metadata Engine
Driven by config.seo and config.youtube settings.
"""

from typing import Dict, Any, List
from core.config import config

def format_seo_package(topic_name: str, facts: List[str], conflict: str, source_url: str, file_number: int) -> Dict[str, Any]:
    """Generates scored title, non-spam description, and category tags based on config."""
    clean_topic = topic_name.replace("(", "").replace(")", "").strip()
    max_title_len = config.seo.title_max_length
    max_desc_len = config.seo.description_max_length
    max_tags = config.seo.tag_max_count

    is_maritime = any(k in f"{topic_name} {' '.join(facts)}".lower() for k in ["ship", "vessel", "maritime", "sea", "ocean", "voyage", "crew", "drift", "arctic"])

    curiosity_titles = [
        f"FILE #{file_number:03d} | The Enigma of {clean_topic[:27]}",
        f"What Really Happened to {clean_topic[:30]}?",
        f"The Unsolved Mystery of {clean_topic[:30]}",
        f"FILE #{file_number:03d} | The Case of {clean_topic[:28]}",
        f"Inside the Mystery: {clean_topic[:32]}"
    ]

    search_titles = [
        f"{clean_topic} Mystery Explained",
        f"The Story of {clean_topic[:35]}",
        f"{clean_topic} Historical Documentary",
        f"What Happened: {clean_topic[:35]}",
        f"{clean_topic} Unsolved Anomaly"
    ]

    hybrid_titles = [
        f"FILE #{file_number:03d} | The Mystery of {clean_topic[:26]} #Shorts",
        f"FILE #{file_number:03d} | Inside {clean_topic[:31]} #Shorts",
        f"{clean_topic[:35]}: The Unsolved Case #Shorts",
        f"The Truth Behind {clean_topic[:28]} #Shorts"
    ]

    if is_maritime:
        hybrid_titles.append(f"{clean_topic[:36]}: The Lost Voyage #Shorts")
        curiosity_titles.append(f"The Ship That Never Returned | FILE #{file_number:03d}")

    all_candidates = hybrid_titles + curiosity_titles + search_titles
    chosen_title = all_candidates[0]
    for cand in all_candidates:
        if len(cand) <= max_title_len:
            chosen_title = cand
            break

    # 2. Structured Non-Spam Documentary Description
    fact_bullets = "\n".join([f"• {f}" for f in facts[:3]])
    summary_lead = facts[0] if facts else f"The official records and documented anomaly of {clean_topic}."
    description = (
        f"📁 NEXUS VAULTS DOSSIER // FILE #{file_number:03d}\n\n"
        f"{summary_lead}\n\n"
        f"DOCUMENTED EVIDENCE:\n"
        f"{fact_bullets}\n\n"
        f"THE UNRESOLVED ANOMALY:\n"
        f"• {conflict}\n\n"
        f"ARCHIVAL SOURCES & RECORDS:\n"
        f"• {source_url}\n\n"
        f"#NexusVaults #Shorts #Documentary"
    )

    if len(description) > max_desc_len:
        description = description[:max_desc_len - 3] + "..."

    topic_words = [w.lower() for w in clean_topic.split() if len(w) > 2 and w.lower() not in ("the", "and", "for", "with")]
    base_tags = ["nexus vaults", "shorts", "documentary", clean_topic.lower()] + topic_words[:3]
    if is_maritime:
        base_tags.extend(["maritime history", "shipwreck", "lost voyage"])
    else:
        base_tags.extend(["investigation", "archival evidence", "historical records"])
    tags = list(dict.fromkeys(base_tags))[:max_tags]

    return {
        "title": chosen_title,
        "description": description,
        "category_id": config.youtube.category_id,
        "tags": tags
    }
