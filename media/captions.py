"""
NEXUS VAULTS 2.0 - Dynamic Phrase-Level Caption Engine
Driven by config.caption and config.render settings.
"""

from pathlib import Path
from typing import List, Dict, Any
from core.config import config

def format_ass_time(seconds: float) -> str:
    """Formats seconds to ASS time format: H:MM:SS.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

def generate_kinetic_ass(word_timings: List[Dict[str, Any]], output_ass_path: Path):
    """
    Generates styled ASS captions with phrase-level grouping and single-word dynamic emphasis.
    """
    w = config.render.width
    h = config.render.height
    font = config.caption.font
    size = config.caption.font_size
    chunk_size = config.caption.words_per_line

    header = f"""[Script Info]
Title: Nexus Vaults Documentary Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Standard,{font},{size},&H00FFFFFF,&H0000D4FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,3,2,60,60,460,1
Style: HookReveal,{font},{size + 6},&H00FFFFFF,&H0000E5FF,&H00000000,&H90000000,-1,0,0,0,100,100,2,0,1,8,4,2,60,60,460,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    total_duration = word_timings[-1]["end"] if word_timings else config.story.target_duration

    for i in range(0, len(word_timings), chunk_size):
        chunk = word_timings[i:i + chunk_size]
        if not chunk:
            continue

        for target_idx, active_word in enumerate(chunk):
            start = format_ass_time(active_word["start"])
            end = format_ass_time(active_word["end"])

            # Hook (0-3s) and Reveal (>total-4s) get high-impact style
            is_hook_or_reveal = (active_word["start"] < 3.2 or active_word["start"] > (total_duration - 4.5))
            style_name = "HookReveal" if is_hook_or_reveal else "Standard"

            # Format words in chunk: only active word gets Gold/Amber emphasis
            line_parts = []
            for j, w_info in enumerate(chunk):
                raw_word = w_info["word"].upper()
                if j == target_idx:
                    # Gold/Amber highlight for the active word
                    line_parts.append(f"{{\\c&H00B0FF&\\fscx108\\fscy108}}{raw_word}{{\\r}}")
                else:
                    # White with slight opacity
                    line_parts.append(f"{{\\c&HFFFFFF&}}{raw_word}{{\\r}}")

            caption_text = " ".join(line_parts)
            events.append(f"Dialogue: 0,{start},{end},{style_name},,0,0,0,,{caption_text}\n")

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.writelines(events)
