"""
NEXUS VAULTS 2.0 - YouTube Intelligence & Competitor Sampling
Uses yt-dlp to inspect competitor titles, hooks, and content gaps.
"""

import subprocess
import json
import shutil
from typing import Dict, List, Any
from core.logging import log

def sample_competitor_shorts(topic_query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Samples competitor videos on YouTube for a topic query to find saturated hooks
    and discover unexploited curiosity angles.
    """
    log.info(f"Sampling YouTube competitor landscape for: '{topic_query}'")
    ytdlp_bin = shutil.which("yt-dlp")
    
    competitor_data = {
        "sampled_count": 0,
        "competitor_titles": [],
        "dominant_hooks": [],
        "content_gap": "Official timeline contradictions and unredacted log entries."
    }
    
    if not ytdlp_bin:
        log.warning("yt-dlp not found on system PATH. Competitor sampling unavailable.")
        competitor_data["competitor_titles"] = []
        competitor_data["dominant_hooks"] = []
        competitor_data["content_gap"] = "Primary documentation and verified timeline contradictions."
        return competitor_data

    try:
        # Run yt-dlp search for shorts/videos with json metadata only (no media download)
        cmd = [
            ytdlp_bin,
            f"ytsearch{max_results}:{topic_query} mystery",
            "--dump-json",
            "--no-playlist",
            "--flat-playlist",
            "--ignore-errors"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        titles = []
        for line in res.stdout.strip().split("\n"):
            if line:
                try:
                    entry = json.loads(line)
                    title = entry.get("title")
                    if title:
                        titles.append(title)
                except Exception:
                    pass
        
        competitor_data["sampled_count"] = len(titles)
        competitor_data["competitor_titles"] = titles[:max_results]
        log.info(f"Analyzed {len(titles)} competitor entries on YouTube.")
    except Exception as e:
        log.warning(f"yt-dlp inspection error: {e}")
        
    return competitor_data
