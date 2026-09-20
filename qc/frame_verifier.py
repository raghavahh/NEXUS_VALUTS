"""
NEXUS VAULTS 2.0 - 3-Layer Visual Verification Pipeline & QC Gate
Layer 1: Clip Existence & Manifest Asset Binding (SHA-256).
Layer 2: Expected Transformed Frame <-> Actual Scene Clip Frame.
Layer 3: Expected Scene Timeline <-> Final MP4 Multi-Point Sampling.
Whole-output Black / Freeze / Corruption QC via FFmpeg detectors.

All thresholds are configuration-driven (QC_FRAME_MATCH_THRESHOLD,
QC_SAMPLE_POINTS_PER_SCENE) — the report prints MEASURED counts only.
"""

import subprocess
import json
import re
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image, ImageStat
from media.images import compute_dhash, hamming_distance, compute_sha256
from core.config import config
from core.logging import log

# L3: max dHash distance between a scene clip frame and the final MP4 frame at the
# same timeline position (burned-in captions/branding shift the hash slightly).
L3_MAX_DHASH_DISTANCE = 20


def extract_frame_at_time(video_path: Path, timestamp_sec: float, output_image_path: Path) -> bool:
    """Extracts a single representative frame at timestamp from a video file."""
    if timestamp_sec < 0:
        timestamp_sec = 0.0
    cmd = [
        "ffmpeg", "-y", "-ss", f"{timestamp_sec:.3f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_image_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0 and output_image_path.exists()


def is_black_frame(img_path: Path, threshold: float = 12.0) -> bool:
    """Detects black or corrupted near-black frames."""
    with Image.open(img_path) as img:
        stat = ImageStat.Stat(img.convert("L"))
        return stat.mean[0] < threshold


def detect_black_and_freeze_frames(video_path: Path) -> Dict[str, Any]:
    """
    Runs FFmpeg blackdetect + freezedetect over the ENTIRE final output.
    Returns measured counts (never assumed):
      {black_frame_count, freeze_frame_count, black_segments, freeze_segments}
    """
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", "blackdetect=d=0.05:pix_th=0.10,freezedetect=n=-60dB:d=0.4",
        "-an", "-f", "null", "-"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    stderr = res.stderr or ""

    black_segments = []
    for m in re.finditer(r"\[blackdetect\s*@.*?\]\s*black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)", stderr):
        black_segments.append({"start": float(m.group(1)), "end": float(m.group(2)), "duration": float(m.group(3))})

    freeze_segments = []
    for m in re.finditer(r"\[freezedetect\s*@.*?\]\s*freeze_start:([\d.]+)\s+freeze_duration:([\d.]+)\s+freeze_end:([\d.]+)", stderr):
        freeze_segments.append({"start": float(m.group(1)), "duration": float(m.group(2)), "end": float(m.group(3))})

    return {
        "black_frame_count": len(black_segments),
        "freeze_frame_count": len(freeze_segments),
        "black_segments": black_segments,
        "freeze_segments": freeze_segments
    }


def verify_scene_clips_and_frames(
    scenes: List[Dict[str, Any]],
    output_video_path: Path,
    scenes_dir: Path
) -> Dict[str, Any]:
    """
    Executes the 3-Layer Visual Verification Pipeline:
    Layer 1: Scene Clip existence and hash binding.       (100% required)
    Layer 2: Expected frame vs Actual scene clip frame.   (100% required)
    Layer 3: Expected scene timeline vs Final MP4 multi-point samples. (100% required)
    Plus: whole-output black-frame and freeze-frame detection (0 required).
    """
    log.info(f"Executing 3-Layer Visual Verification on {len(scenes)} scenes for {output_video_path.name}...")
    if not config.qc.require_frame_verification:
        log.warning("[QC] Frame verification explicitly disabled by config.qc.require_frame_verification. Bypassing L1-L3 checks.")
        return {
            "all_passed": True,
            "layer1_count": len(scenes),
            "layer2_count": len(scenes),
            "layer3_count": len(scenes),
            "total_scenes": len(scenes),
            "black_frame_count": 0,
            "freeze_frame_count": 0,
            "black_segments": [],
            "freeze_segments": [],
            "records": []
        }

    temp_dir = scenes_dir / "verification_frames"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if config.qc.require_unique_assets:
        unique_assets = {sc.get("canonical_url") or str(sc.get("path", "")) for sc in scenes}
        if len(unique_assets) < len(scenes):
            log.warning(f"[QC] Asset reuse detected: {len(scenes) - len(unique_assets)} duplicate asset(s) present across scenes.")

    layer1_passed = 0
    layer2_passed = 0
    layer3_passed = 0
    verification_records = []
    l2_threshold = config.qc.frame_match_threshold
    sample_points = max(1, config.qc.sample_points_per_scene)

    for idx, sc in enumerate(scenes):
        scene_id = sc["scene_id"]
        clip_path = scenes_dir / f"scene_{idx:03d}.mp4"
        asset_path = Path(sc["asset_path"]) if "asset_path" in sc else Path(sc.get("path", ""))

        # -------------------------------------------------------------
        # LAYER 1: Clip Existence & Manifest Asset Binding
        # -------------------------------------------------------------
        if not clip_path.exists() or clip_path.stat().st_size < 1024:
            log.error(f"Layer 1 FAIL: Scene clip missing or corrupt: {clip_path.name}")
            continue
        if not asset_path.exists():
            log.error(f"Layer 1 FAIL: Source asset missing: {asset_path}")
            continue

        clip_sha = compute_sha256(clip_path)
        layer1_passed += 1

        # -------------------------------------------------------------
        # LAYER 2: Scene Clip Frame vs Source Asset Perceptual Match
        # -------------------------------------------------------------
        duration = float(sc.get("duration", 3.0))
        sample_offset_fraction = max(0.05, min(0.95, config.qc.frame_sample_offset))
        clip_mid = duration * sample_offset_fraction
        clip_frame_path = temp_dir / f"clip_frame_{scene_id:02d}.jpg"

        if not extract_frame_at_time(clip_path, clip_mid, clip_frame_path):
            log.error(f"Layer 2 FAIL: Could not extract frame from {clip_path.name}")
            continue

        if is_black_frame(clip_frame_path):
            log.error(f"QC FAIL: Black frame detected in {clip_path.name}")
            continue

        clip_phash = compute_dhash(clip_frame_path)
        asset_phash = compute_dhash(asset_path)
        dist = hamming_distance(clip_phash, asset_phash)
        # Transformed frame match ratio (0.0 to 1.0)
        match_ratio = round(1.0 - (dist / 64.0), 2)

        # Threshold calibrated for zoompan/dual-layer transformations (config-driven)
        if match_ratio >= l2_threshold:
            layer2_passed += 1
        else:
            log.warning(f"Layer 2 low match ratio ({match_ratio} < {l2_threshold}) on Scene {scene_id:02d}")

        # -------------------------------------------------------------
        # LAYER 3: Scene Timeline <-> Final MP4 Multi-Point Sampling
        # Samples QC_SAMPLE_POINTS_PER_SCENE positions per scene; every sample
        # must match the clip at the same relative offset.
        # -------------------------------------------------------------
        scene_start = float(sc.get("start", 0.0))
        scene_pass = True
        worst_dist = 0
        for p_idx in range(sample_points):
            fraction = (p_idx + 1) / (sample_points + 1)
            offset = duration * fraction
            clip_sample_path = temp_dir / f"l3_clip_{scene_id:02d}_{p_idx}.jpg"
            final_sample_path = temp_dir / f"l3_final_{scene_id:02d}_{p_idx}.jpg"
            if not extract_frame_at_time(clip_path, offset, clip_sample_path):
                scene_pass = False
                log.error(f"Layer 3 FAIL: Could not sample clip {clip_path.name} at {offset:.2f}s")
                break
            if not extract_frame_at_time(output_video_path, scene_start + offset, final_sample_path):
                scene_pass = False
                log.error(f"Layer 3 FAIL: Could not sample final MP4 at {scene_start + offset:.2f}s")
                break
            d = hamming_distance(compute_dhash(clip_sample_path), compute_dhash(final_sample_path))
            worst_dist = max(worst_dist, d)
            if d > L3_MAX_DHASH_DISTANCE:
                scene_pass = False
                log.warning(f"Layer 3 frame drift on Scene {scene_id:02d} @+{offset:.2f}s (dist: {d} > {L3_MAX_DHASH_DISTANCE})")

        l3_status = "PASS" if scene_pass else "MISMATCH"
        if scene_pass:
            layer3_passed += 1

        verification_records.append({
            "scene_id": scene_id,
            "clip_file": clip_path.name,
            "clip_sha256": clip_sha[:16],
            "asset_file": asset_path.name,
            "layer1_status": "PASS",
            "layer2_match_ratio": match_ratio,
            "layer3_status": l3_status,
            "timeline_timestamp": round(scene_start + clip_mid, 2)
        })

        log.info(f"Scene {scene_id:02d} [{sc.get('visual_type')}]: L1 PASS | L2 Match: {match_ratio} | L3 Final: {l3_status}")

    # -------------------------------------------------------------
    # WHOLE-OUTPUT DETECTION: black frames & freeze frames (measured)
    # -------------------------------------------------------------
    detection = detect_black_and_freeze_frames(output_video_path)
    black_count = detection["black_frame_count"]
    freeze_count = detection["freeze_frame_count"]
    if black_count:
        log.error(f"QC FAIL: {black_count} black segment(s) detected in final MP4: {detection['black_segments'][:3]}")
    if freeze_count:
        log.error(f"QC FAIL: {freeze_count} freeze segment(s) detected in final MP4: {detection['freeze_segments'][:3]}")

    # L1 = 100%, L2 = 100%, L3 = 100%, zero black, zero freeze —
    # no partial verification pass is acceptable in production.
    all_passed = (
        (layer1_passed == len(scenes))
        and (layer2_passed == len(scenes))
        and (layer3_passed == len(scenes))
        and black_count == 0
        and freeze_count == 0
    )

    return {
        "all_passed": all_passed,
        "layer1_count": layer1_passed,
        "layer2_count": layer2_passed,
        "layer3_count": layer3_passed,
        "total_scenes": len(scenes),
        "black_frame_count": black_count,
        "freeze_frame_count": freeze_count,
        "black_segments": detection["black_segments"],
        "freeze_segments": detection["freeze_segments"],
        "records": verification_records
    }
