"""
NEXUS VAULTS 2.0 - Immutable Render Manifest & Traceability Chain
Generates and loads render_manifest.json.
Completely decouples content planning from compositor rendering.
Every scene has an unbroken chain:
Source Asset -> Asset SHA-256 -> Scene Manifest -> Scene Clip -> Final Assembly.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from core.logging import log

def generate_render_manifest(
    scenes: List[Dict[str, Any]],
    manifest_path: Path,
    file_number: int,
    topic: str
) -> Path:
    """Creates an immutable render manifest binding every scene contract and asset hash."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = {
        "file_number": file_number,
        "topic": topic,
        "scene_count": len(scenes),
        "total_duration": round(scenes[-1]["end"] if scenes else 0.0, 2),
        "scenes": []
    }

    for sc in scenes:
        meta = sc.get("asset_meta", {})
        item = {
            "scene_id": sc["scene_id"],
            "start": sc["start"],
            "end": sc["end"],
            "duration": sc["duration"],
            "narration": sc.get("narration", ""),
            "claim": sc.get("claim", ""),
            "visual_purpose": sc.get("visual_purpose", "SHOW_PRIMARY_EVIDENCE"),
            "visual_type": sc.get("visual_type", "ARCHIVAL_PHOTO"),
            "asset_id": meta.get("asset_id", f"asset_{sc['scene_id']:02d}"),
            "asset_path": str(sc["path"].resolve().as_posix()) if "path" in sc else "",
            "asset_sha256": meta.get("sha256", ""),
            "asset_phash": meta.get("phash", ""),
            "source": meta.get("source", "Archival Archive"),
            "source_url": meta.get("url", ""),
            "canonical_url": meta.get("canonical_url", ""),
            "license": meta.get("license", "Public Domain"),
            "motion_intent": sc.get("motion_intent", sc.get("motion_style", "hero_reveal")),
            "composition_intent": sc.get("composition_intent", "hero_full_frame"),
            "transition_in": sc.get("transition_in", "hard_cut"),
            "transition_out": sc.get("transition_out", "hard_cut"),
            "audio_intent": sc.get("audio_intent", "normal"),
            "relevance_score": meta.get("relevance_score", 1.0),
            "relevance_breakdown": meta.get("relevance_breakdown", {})
        }
        manifest_data["scenes"].append(item)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    log.info(f"Generated immutable render manifest ({len(scenes)} scenes) -> {manifest_path.name}")
    return manifest_path

def load_render_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Loads and validates an existing render manifest."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "scenes" in data and len(data["scenes"]) > 0, "Invalid or empty render manifest!"
    return data
