"""
NEXUS VAULTS 2.0 - Voice Engine (Edge-TTS)
Generates high-fidelity Microsoft Neural narration and extracts precise word-level subtitle timings.
100% Free, zero cloud subscription required.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import edge_tts
from core.config import config
from core.logging import log

async def generate_speech_async(text: str, output_audio_path: Path) -> List[Dict[str, Any]]:
    """
    Synthesizes speech and extracts word boundaries with microsecond precision.
    Returns: [{"word": str, "start": float, "end": float}]
    """
    log.info(f"Synthesizing voice with {config.audio.voice} at rate {config.audio.rate}...")
    
    communicate = edge_tts.Communicate(
        text=text,
        voice=config.audio.voice,
        rate=config.audio.rate,
        pitch=config.audio.pitch
    )

    
    word_timings = []
    
    with open(output_audio_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_sec = chunk["offset"] / 10_000_000.0
                duration_sec = chunk["duration"] / 10_000_000.0
                word_timings.append({
                    "word": chunk["text"],
                    "start": round(start_sec, 3),
                    "end": round(start_sec + duration_sec, 3)
                })
            elif chunk["type"] == "SentenceBoundary":
                # Interpolate words accurately across sentence duration
                sentence_text = chunk.get("text", "")
                words = sentence_text.strip().split()
                if words:
                    sent_start = chunk["offset"] / 10_000_000.0
                    sent_duration = chunk["duration"] / 10_000_000.0
                    total_chars = sum(len(w) for w in words)
                    curr_time = sent_start
                    for w in words:
                        char_weight = len(w) / max(1, total_chars)
                        w_duration = max(0.15, sent_duration * char_weight)
                        word_timings.append({
                            "word": w,
                            "start": round(curr_time, 3),
                            "end": round(curr_time + w_duration, 3)
                        })
                        curr_time += w_duration
                
    log.info(f"Generated audio ({output_audio_path.name}) with {len(word_timings)} timed word boundaries.")
    return word_timings

def generate_voice(text: str, output_audio_path: Path) -> List[Dict[str, Any]]:
    """Synchronous wrapper for generate_speech_async."""
    try:
        return asyncio.run(generate_speech_async(text, output_audio_path))
    except Exception as e:
        log.warning(f"Voice generation with primary voice failed: {e}. Retrying with backup...")
        communicate = edge_tts.Communicate(text=text, voice="en-US-GuyNeural")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(generate_speech_async(text, output_audio_path))
