"""
NEXUS VAULTS 2.0 - Editorial Motion Compositor & Manifest Renderer
Strict Rules:
1. Consumes render_manifest.json ONLY. Zero asset selection in compositor.
2. Asset-Adaptive Motion:
   - PORTRAIT: Slow push toward subject face + subtle lateral drift.
   - DOCUMENT: Readability-first vertical inspection scroll with framed elevation.
   - MAP: Clean analytical route tracking.
   - DIAGRAM: Technical mechanism punch-in.
   - ARCHIVAL_PHOTO: Restrained parallax + subtle archival vignette.
   - ATMOSPHERIC: Natural cinematic depth zoom.
3. Enforces strictly identical stream encoding across all individual scene clips.
4. Robust Concat Engine: Verifies clip stream compatibility; uses instant stream copy if verified, with controlled re-encode fallback.
"""

import subprocess
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any
from core.config import config
from core.logging import log

def get_media_duration(file_path: Path) -> float:
    """Returns real media duration in seconds. Raises on failure — a faked
    duration would silently corrupt scene timing and the duration QC gate."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", str(file_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(res.stdout)
        return float(data["format"]["duration"])
    except Exception:
        raise RuntimeError(
            f"FFprobe could not determine duration of {file_path} "
            f"(exit {res.returncode}). Media file is missing or corrupt — "
            "production cannot proceed with an unverifiable duration."
        )

def verify_clip_compatibility(clips: List[Path]) -> bool:
    """Verifies that all scene clips share identical resolution, codec, and pixel format."""
    if not clips:
        return False
    ref_props = None
    for clip in clips:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate",
            "-of", "json", str(clip)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        try:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            if not streams:
                return False
            props = streams[0]
            if ref_props is None:
                ref_props = props
            else:
                for k in ("codec_name", "width", "height", "pix_fmt", "r_frame_rate"):
                    if props.get(k) != ref_props.get(k):
                        log.warning(f"Stream mismatch on {clip.name} ({k}: {props.get(k)} vs {ref_props.get(k)})")
                        return False
        except Exception:
            return False
    return True

def build_scene_segment(scene: Dict[str, Any], output_segment_path: Path, scene_idx: int) -> Path:
    """
    Renders an individual scene using asset-adaptive motion and composition.
    Enforces identical stream parameters (1080x1920 @ 30fps yuv420p libx264).
    """
    img_path = str(Path(scene["asset_path"]).resolve()).replace("\\", "/")
    duration = float(scene["duration"])
    motion = scene.get("motion_intent", scene.get("motion_style", "hero_reveal")).lower()
    vtype = scene.get("visual_type", "ARCHIVAL_PHOTO").upper()
    comp = scene.get("composition_intent", "dual_layer_framed").lower()

    w = config.render.width
    h = config.render.height
    fps = config.render.fps
    codec = config.render.codec
    crf = config.render.crf
    preset = config.render.preset
    frames = max(1, int(round(duration * fps)))

    # Asset-Adaptive Motion Choreography
    if vtype == "PORTRAIT" or motion == "portrait_slow_push":
        # Slow dramatic push focused toward upper-center (face)
        pan_filter = f"zoompan=z='min(1.02+0.001*on,1.14)':x='iw/2-(iw/zoom/2)':y='ih*0.15':d={frames}:s={w}x{h}:fps={fps}"
    elif vtype in ("DOCUMENT", "NEWSPAPER") or motion == "document_inspection_scroll":
        # Readability-first: Top-to-bottom investigative vertical inspection
        pan_filter = f"zoompan=z=1.12:y='if(lte(on,1),0,y+1.4)':d={frames}:s={w}x{h}:fps={fps}"
    elif vtype in ("MAP", "ROUTE_MAP") or motion == "map_directional_track":
        # Clean analytical route travel / horizontal tracking
        pan_filter = f"zoompan=z=1.12:x='if(lte(on,1),0,x+1.6)':d={frames}:s={w}x{h}:fps={fps}"
    elif vtype == "DIAGRAM" or motion == "diagram_punch_in":
        # Technical mechanism punch-in zoom
        pan_filter = f"zoompan=z='min(1.0+0.0022*on,1.22)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif motion == "evidence_focus":
        pan_filter = f"zoompan=z='min(1.05+0.002*on,1.25)':x='iw*0.25':y='ih*0.25':d={frames}:s={w}x{h}:fps={fps}"
    elif motion == "depth_zoom":
        pan_filter = f"zoompan=z='min(1.0+0.0016*on,1.16)':d={frames}:s={w}x{h}:fps={fps}"
    elif motion == "horizontal_camera":
        pan_filter = f"zoompan=z=1.10:x='if(lte(on,1),0,x+1.4)':d={frames}:s={w}x{h}:fps={fps}"
    elif motion == "vertical_camera":
        pan_filter = f"zoompan=z=1.10:y='if(lte(on,1),0,y+1.4)':d={frames}:s={w}x{h}:fps={fps}"
    else:  # hero_reveal or default
        pan_filter = f"zoompan=z='min(1.15-0.0012*on,1.03)':d={frames}:s={w}x{h}:fps={fps}"

    # Style Treatment Filter Chain
    vignette_expr = ""
    if config.scene.adaptive_style:
        if vtype == "ARCHIVAL_PHOTO":
            vignette_expr = ",vignette=PI/4:mode=backward"
        elif vtype == "PORTRAIT":
            vignette_expr = ",vignette=PI/5:mode=backward"

    # Editorial Composition Framing
    fg_w = int(w * 0.92)
    fg_h = int(h * 0.78)
    pad_w = fg_w + 20
    pad_h = fg_h + 20

    if comp == "hero_full_frame":
        # Full-frame treatment for high-impact archival photos
        filter_complex = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},{pan_filter}{vignette_expr},format=yuv420p[out]"
    else:
        # Dual-layer framed composition with sharp elevated document/portrait
        filter_complex = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:3,colorchannelmixer=aa=0.4[bg];"
            f"[0:v]scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease,pad={pad_w}:{pad_h}:10:10:color=white@0.2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[comp];"
            f"[comp]{pan_filter}{vignette_expr},format=yuv420p[out]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", img_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-frames:v", str(frames),
        "-r", str(fps),
        "-pix_fmt", config.render.pixel_format,
        "-c:v", codec,
        "-profile:v", "high",
        "-level:v", "4.0",
        "-preset", preset,
        "-crf", crf,
        str(output_segment_path)
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        log.error(f"FFmpeg scene render error for Scene {scene_idx} ({img_path}): {e.stderr}")
        raise
    return output_segment_path

def build_composite_video_from_manifest(
    manifest_data: Dict[str, Any],
    mixed_audio_path: Path,
    ass_subtitle_path: Path,
    output_video_path: Path,
    file_number: int
) -> Path:
    """
    Renders every individual scene clip into config.storage.temp_dir/scenes_{file_number}/
    strictly following manifest directives, then verifies compatibility and assembles the broadcast master.
    """
    scenes = manifest_data.get("scenes", [])
    log.info(f"Compositor executing manifest: {len(scenes)} distinct multi-composition scenes...")
    scenes_dir = config.storage.temp_dir / f"scenes_{file_number:03d}"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    segment_files = []

    # 1. Render each scene clip with manifest-assigned motion and composition
    for idx, scene in enumerate(scenes):
        seg_file = scenes_dir / f"scene_{idx:03d}.mp4"
        build_scene_segment(scene, seg_file, idx)
        segment_files.append(seg_file)
        scene["rendered_clip_path"] = str(seg_file.resolve().as_posix())

    log.info(f"All {len(segment_files)} individual scene clips rendered into {scenes_dir.name}")

    # 2. Concat all distinct scene segments
    concat_list = scenes_dir / "concat_timeline.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for seg in segment_files:
            f.write(f"file '{seg.resolve().as_posix()}'\n")

    raw_merged = scenes_dir / "merged_scenes.mp4"
    is_compatible = verify_clip_compatibility(segment_files)

    if is_compatible:
        log.info("Verified identical clip stream parameters. Executing instant stream-copy concatenation.")
        concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(raw_merged)
        ]
    else:
        log.warning("Stream parameter discrepancy detected. Performing controlled re-encode concatenation.")
        concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", config.render.codec, "-preset", config.render.preset, "-crf", config.render.crf,
            "-pix_fmt", config.render.pixel_format,
            str(raw_merged)
        ]

    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 3. Master Burn: Kinetic Subtitles + Archival Dossier Badge
    clean_ass = ass_subtitle_path.resolve().as_posix().replace(":", "\\:")
    header_text = f"FILE #{file_number:03d} | INVESTIGATION ARCHIVE"

    final_filter = (
        f"[0:v]drawbox=y=0:color=black@0.75:width=iw:height=140:t=fill,"
        f"drawtext=text='NEXUS VAULTS | {header_text}':fontcolor=white:fontsize=36:"
        f"x=(w-text_w)/2:y=50:font='Arial Black',"
        f"subtitles='{clean_ass}'[v]"
    )

    master_cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_merged),
        "-i", str(mixed_audio_path),
        "-filter_complex", final_filter,
        "-map", "[v]", "-map", "1:a",
        "-c:v", config.render.codec, "-preset", config.render.preset, "-crf", config.render.crf,
        "-c:a", config.render.audio_codec, "-b:a", config.render.audio_bitrate,
        "-shortest",
        str(output_video_path)
    ]
    subprocess.run(master_cmd, check=True)

    log.info(f"Broadcast Master Rendered: {output_video_path.name} ({output_video_path.stat().st_size / (1024*1024):.2f} MB)")
    return output_video_path
