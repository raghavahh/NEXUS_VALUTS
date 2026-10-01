"""
AI Video Factory - Documentary SEO & Metadata Engine
Driven by config.seo, config.youtube settings, and Channel Brain.
"""

from typing import Dict, Any, List
from core.config import config
from core.channel_brain import get_channel_brain


def format_seo_package(topic_name: str, facts: List[str], conflict: str, source_url: str, file_number: int) -> Dict[str, Any]:
    """Generates scored title, non-spam description, and category tags based on config and Channel Brain."""
    brain = get_channel_brain()
    channel_name = brain.profile.name or "AI Video Factory"
    channel_handle = brain.profile.handle or "aivideofactory"
    channel_niche = brain.profile.niche or "documentary"
    
    clean_topic = topic_name.replace("(", "").replace(")", "").strip()
    max_title_len = config.seo.title_max_length
    max_desc_len = config.seo.description_max_length
    max_tags = config.seo.tag_max_count

    is_maritime = any(k in f"{topic_name} {' '.join(facts)}".lower() for k in ["ship", "vessel", "maritime", "sea", "ocean", "voyage", "crew", "drift", "arctic"])

    curiosity_titles = [
        f"VIDEO #{file_number:03d} | The Enigma of {clean_topic[:27]}",
        f"What Really Happened to {clean_topic[:30]}?",
        f"The Unexplained Case of {clean_topic[:30]}",
        f"VIDEO #{file_number:03d} | The Case of {clean_topic[:28]}",
        f"Inside the Anomaly: {clean_topic[:32]}"
    ]

    search_titles = [
        f"{clean_topic} Explained",
        f"The Story of {clean_topic[:35]}",
        f"{clean_topic} Documentary",
        f"What Happened: {clean_topic[:35]}",
        f"{clean_topic} Anomaly"
    ]

    hybrid_titles = [
        f"VIDEO #{file_number:03d} | The Mystery of {clean_topic[:26]} #Shorts",
        f"VIDEO #{file_number:03d} | Inside {clean_topic[:31]} #Shorts",
        f"{clean_topic[:35]}: The Unexplained Case #Shorts",
        f"The Truth Behind {clean_topic[:28]} #Shorts"
    ]

    if is_maritime:
        hybrid_titles.append(f"{clean_topic[:36]}: The Lost Voyage #Shorts")
        curiosity_titles.append(f"The Ship That Never Returned | VIDEO #{file_number:03d}")

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
        f"{channel_name} | VIDEO #{file_number:03d}\n\n"
        f"{summary_lead}\n\n"
        f"DOCUMENTED EVIDENCE:\n"
        f"{fact_bullets}\n\n"
        f"THE UNRESOLVED ANOMALY:\n"
        f"• {conflict}\n\n"
        f"ARCHIVAL SOURCES & RECORDS:\n"
        f"• {source_url}\n\n"
        f"#{channel_name.replace(' ', '')} #Shorts #Documentary"
    )

    if len(description) > max_desc_len:
        description = description[:max_desc_len - 3] + "..."

    topic_words = [w.lower() for w in clean_topic.split() if len(w) > 2 and w.lower() not in ("the", "and", "for", "with")]
    base_tags = [channel_name.lower().replace(' ', ''), "shorts", channel_niche.lower(), clean_topic.lower()] + topic_words[:3]
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
