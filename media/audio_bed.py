"""
NEXUS VAULTS 2.0 - Cinematic Atmospheric Audio Engine & Mastering Stage
Implements:
1. Multi-layered atmospheric drone bed (level set once, by config).
2. Narration ducking via FFmpeg sidechaincompress (ambient attenuated under speech).
3. Professional mastering stage using FFmpeg loudnorm for EBU R128-based loudness
   normalization with true-peak ceiling control.
4. Post-master loudness MEASUREMENT so the production report prints measured
   LUFS, never an assumed value.
"""

import subprocess
import re
from pathlib import Path
from core.config import config
from core.logging import log

def generate_ambient_drone(duration_sec: float, output_ambient_path: Path) -> Path:
    """Generates an atmospheric tension drone bed via FFmpeg lavfi using configured volume.
    The configured AUDIO_BACKGROUND_VOLUME is the FINAL ambient level — the mixer
    must not attenuate it a second time."""
    bg_vol = config.audio.background_volume
    # Dual-tone drone: 55Hz root + 82.5Hz fifth with lowpass filter
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"sine=frequency=55:duration={int(duration_sec + 3)}",
        "-f", "lavfi",
        "-i", f"sine=frequency=82.5:duration={int(duration_sec + 3)}",
        "-filter_complex",
        f"[0:a][1:a]amix=inputs=2:duration=shortest,lowpass=f=160,volume={bg_vol}dB[bg]",
        "-map", "[bg]",
        "-c:a", "libmp3lame", str(output_ambient_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_ambient_path

def mix_and_master_audio(voice_path: Path, ambient_path: Path, output_mixed_path: Path) -> Path:
    """
    Mixes voice narration with ambient drone, applies real sidechain ducking
    (ambient compressed under the narration signal), and executes EBU R128-based
    loudnorm mastering with true-peak ceiling control.
    """
    voice_vol = config.audio.voice_volume
    # Sidechain compression ratio derived from the configured ducking attenuation
    # (e.g. -26 dB attenuation -> ratio 13). Bounded to a sane 2..20 range.
    duck_ratio = max(2.0, min(20.0, abs(config.audio.ducking_attenuation_db) / 2.0))
    i_target = config.audio.loudnorm_i
    tp_target = config.audio.loudnorm_tp
    lra_target = config.audio.loudnorm_lra

    # Filter chain:
    # 1. Voice gain per config (AUDIO_VOICE_VOLUME)
    # 2. Ambient stays at its configured level; sidechain-compressed by voice
    # 3. Mastering stage: loudnorm for EBU R128 loudness measurement & normalization
    filter_chain = (
        f"[0:a]volume={voice_vol}dB[v];"
        f"[1:a]volume=1.0[bg];"
        f"[bg][v]sidechaincompress=threshold=0.03:ratio={duck_ratio:.1f}:attack=50:release=400[bgd];"
        f"[v][bgd]amix=inputs=2:duration=first:dropout_transition=2,"
        f"loudnorm=I={i_target}:TP={tp_target}:LRA={lra_target}[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(voice_path),
        "-i", str(ambient_path),
        "-filter_complex", filter_chain,
        "-map", "[a]",
        "-c:a", config.render.audio_codec,
        "-b:a", config.render.audio_bitrate,
        str(output_mixed_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    log.info(f"Broadcast audio mixed and mastered (EBU R128 target {i_target} LUFS, TP {tp_target} dB) -> {output_mixed_path.name}")
    return output_mixed_path


def measure_master_loudness(media_path: Path) -> float | None:
    """
    Measures the ACTUAL integrated loudness (LUFS) of a media file's audio track
    using FFmpeg ebur128. Returns None if measurement fails — callers must report
    'NOT MEASURED' rather than inventing a value.
    """
    cmd = [
        "ffmpeg", "-nostats", "-i", str(media_path),
        "-af", "ebur128",
        "-f", "null", "-"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Extract the integrated loudness from the final Summary block
        m = re.search(r"Summary:.*?Integrated loudness:\s*\n\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", res.stderr or "", re.DOTALL)
        if m:
            return round(float(m.group(1)), 1)
        matches = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", res.stderr or "")
        if matches:
            return round(float(matches[-1]), 1)
    except Exception as e:
        log.debug(f"Loudness measurement failed for {media_path}: {e}")
    return None
