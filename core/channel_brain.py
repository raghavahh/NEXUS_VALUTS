"""
AI Video Factory - Channel Brain
Centralized channel intelligence: Profile, Creative Directive, Learning Memory,
Format Preferences, and Publishing Preferences.
Single source of truth for all AI content stages.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.config import config
from core.logging import log


@dataclass
class ChannelProfile:
    """Who/what the channel is."""
    name: str = ""
    handle: str = ""
    description: str = ""
    niche: str = ""
    audience: str = ""
    language: str = "en"
    region: str = "US"


@dataclass
class CreativeDirective:
    """How the channel should think/create. Free-form user-editable field."""
    directive: str = ""
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def update(self, new_directive: str):
        self.directive = new_directive.strip()
        self.updated_at = datetime.utcnow().isoformat() + "Z"


@dataclass
class LearningMemory:
    """Persistent knowledge derived from content history and analytics."""
    recent_topics: List[str] = field(default_factory=list)
    topic_performance: Dict[str, float] = field(default_factory=dict)
    hook_performance: Dict[str, float] = field(default_factory=dict)
    format_performance: Dict[str, float] = field(default_factory=dict)
    successful_patterns: List[str] = field(default_factory=list)
    failed_patterns: List[str] = field(default_factory=list)
    audience_signals: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def add_topic(self, topic: str, performance: float = 0.0):
        if topic not in self.recent_topics:
            self.recent_topics.insert(0, topic)
            self.recent_topics = self.recent_topics[:50]
        if performance:
            self.topic_performance[topic] = performance
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def add_hook_performance(self, hook_type: str, score: float):
        self.hook_performance[hook_type] = score
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def add_format_performance(self, format_type: str, score: float):
        self.format_performance[format_type] = score
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def record_success(self, pattern: str):
        if pattern not in self.successful_patterns:
            self.successful_patterns.insert(0, pattern)
            self.successful_patterns = self.successful_patterns[:20]
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def record_failure(self, pattern: str):
        if pattern not in self.failed_patterns:
            self.failed_patterns.insert(0, pattern)
            self.failed_patterns = self.failed_patterns[:20]
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def update_audience_signal(self, key: str, value: Any):
        self.audience_signals[key] = value
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def get_compact_context(self, max_chars: int = 2000) -> str:
        """Returns compact memory context for prompt injection."""
        parts = []
        
        if self.recent_topics:
            parts.append(f"Recent topics: {', '.join(self.recent_topics[:10])}")
        
        if self.topic_performance:
            top_topics = sorted(self.topic_performance.items(), key=lambda x: x[1], reverse=True)[:5]
            parts.append(f"Top performing topics: {', '.join([f'{t} ({s:.2f})' for t, s in top_topics])}")
        
        if self.hook_performance:
            top_hooks = sorted(self.hook_performance.items(), key=lambda x: x[1], reverse=True)[:3]
            parts.append(f"Effective hook types: {', '.join([f'{h} ({s:.2f})' for h, s in top_hooks])}")
        
        if self.format_performance:
            top_formats = sorted(self.format_performance.items(), key=lambda x: x[1], reverse=True)[:3]
            parts.append(f"Effective formats: {', '.join([f'{f} ({s:.2f})' for f, s in top_formats])}")
        
        if self.successful_patterns:
            parts.append(f"Successful patterns: {'; '.join(self.successful_patterns[:5])}")
        
        if self.failed_patterns:
            parts.append(f"Patterns to avoid: {'; '.join(self.failed_patterns[:5])}")
        
        if self.audience_signals:
            parts.append(f"Audience signals: {json.dumps(self.audience_signals, separators=(',', ':'))}")
        
        context = "\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "..."
        return context


@dataclass
class FormatPreferences:
    """Video format configuration."""
    format_type: str = "shorts"
    target_duration_sec: int = 60
    aspect_ratio: str = "9:16"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    caption_style: str = "kinetic"
    words_per_line: int = 3


@dataclass
class PublishingPreferences:
    """Publishing configuration."""
    timezone: str = "America/New_York"
    upload_hour: int = 12
    upload_minute: int = 0
    min_upload_gap_hours: int = 18
    privacy: str = "private"
    schedule_behavior: str = "daily"
    category_id: str = "28"
    default_language: str = "en"
    ready_buffer_minutes: int = 60


@dataclass
class ChannelBrain:
    """
    Unified Channel Brain - single source of truth for channel identity,
    creative direction, learning memory, and preferences.
    """
    profile: ChannelProfile = field(default_factory=ChannelProfile)
    creative_directive: CreativeDirective = field(default_factory=CreativeDirective)
    learning_memory: LearningMemory = field(default_factory=LearningMemory)
    format_prefs: FormatPreferences = field(default_factory=FormatPreferences)
    publishing_prefs: PublishingPreferences = field(default_factory=PublishingPreferences)
    version: int = 1
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "profile": asdict(self.profile),
            "creative_directive": asdict(self.creative_directive),
            "learning_memory": asdict(self.learning_memory),
            "format_prefs": asdict(self.format_prefs),
            "publishing_prefs": asdict(self.publishing_prefs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelBrain":
        brain = cls()
        if "version" in data:
            brain.version = data["version"]
        if "updated_at" in data:
            brain.updated_at = data["updated_at"]
        if "profile" in data:
            brain.profile = ChannelProfile(**data["profile"])
        if "creative_directive" in data:
            brain.creative_directive = CreativeDirective(**data["creative_directive"])
        if "learning_memory" in data:
            brain.learning_memory = LearningMemory(**data["learning_memory"])
        if "format_prefs" in data:
            brain.format_prefs = FormatPreferences(**data["format_prefs"])
        if "publishing_prefs" in data:
            brain.publishing_prefs = PublishingPreferences(**data["publishing_prefs"])
        return brain

    def get_prompt_context(self, task: str = "general", max_chars: int = 3000) -> str:
        """
        Builds the Channel Brain context for LLM prompts.
        Includes profile, creative directive, and relevant learning memory.
        """
        parts = []

        # Channel Profile
        profile_parts = []
        if self.profile.name:
            profile_parts.append(f"Channel Name: {self.profile.name}")
        if self.profile.handle:
            profile_parts.append(f"Handle: @{self.profile.handle}")
        if self.profile.description:
            profile_parts.append(f"Description: {self.profile.description}")
        if self.profile.niche:
            profile_parts.append(f"Niche: {self.profile.niche}")
        if self.profile.audience:
            profile_parts.append(f"Target Audience: {self.profile.audience}")
        if self.profile.language:
            profile_parts.append(f"Language: {self.profile.language}")
        if self.profile.region:
            profile_parts.append(f"Region: {self.profile.region}")
        
        if profile_parts:
            parts.append("CHANNEL PROFILE:\n" + "\n".join(profile_parts))

        # Creative Directive
        if self.creative_directive.directive:
            parts.append(f"CREATIVE DIRECTIVE:\n{self.creative_directive.directive}")

        # Learning Memory (compact)
        memory_context = self.learning_memory.get_compact_context(max_chars=1500)
        if memory_context:
            parts.append(f"LEARNING MEMORY:\n{memory_context}")

        # Format Preferences (task-relevant)
        if task in ("story", "scene", "visual", "seo", "hooks", "research"):
            fmt = self.format_prefs
            fmt_parts = [
                f"Format: {fmt.format_type}",
                f"Target Duration: {fmt.target_duration_sec}s",
                f"Aspect Ratio: {fmt.aspect_ratio}",
                f"Resolution: {fmt.width}x{fmt.height} @ {fmt.fps}fps",
            ]
            if fmt.caption_style:
                fmt_parts.append(f"Caption Style: {fmt.caption_style}")
            parts.append("FORMAT PREFERENCES:\n" + "\n".join(fmt_parts))

        # Publishing Preferences (for SEO/scheduling tasks)
        if task in ("seo", "publish", "schedule"):
            pub = self.publishing_prefs
            pub_parts = [
                f"Category ID: {pub.category_id}",
                f"Default Language: {pub.default_language}",
                f"Privacy: {pub.privacy}",
                f"Schedule: {pub.schedule_behavior} at {pub.upload_hour:02d}:{pub.upload_minute:02d} {pub.timezone}",
            ]
            parts.append("PUBLISHING PREFERENCES:\n" + "\n".join(pub_parts))

        context = "\n\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "\n[TRUNCATED]"
        return context


# Global instance and persistence
_CHANNEL_BRAIN: Optional[ChannelBrain] = None
_BRAIN_PATH = config.storage.state_dir / "channel_brain.json"


def get_channel_brain() -> ChannelBrain:
    """Returns the singleton Channel Brain instance, loading from disk if needed."""
    global _CHANNEL_BRAIN
    if _CHANNEL_BRAIN is None:
        _CHANNEL_BRAIN = _load_brain()
    return _CHANNEL_BRAIN


def _load_brain() -> ChannelBrain:
    """Loads Channel Brain from JSON file, or creates default if not found."""
    if _BRAIN_PATH.exists():
        try:
            with open(_BRAIN_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            brain = ChannelBrain.from_dict(data)
            log.info(f"Loaded Channel Brain v{brain.version} from {_BRAIN_PATH}")
            return brain
        except Exception as e:
            log.warning(f"Failed to load Channel Brain: {e}. Creating new default.")
    else:
        log.info("No Channel Brain found. Creating new default.")

    # Environment variables make first-time CI setup deterministic without
    # requiring a generated state file to be committed.
    brain = ChannelBrain()
    profile = brain.profile
    profile.name = os.getenv("CHANNEL_NAME", "").strip()
    profile.handle = os.getenv("CHANNEL_HANDLE", "").strip().lstrip("@")
    profile.description = os.getenv("CHANNEL_DESCRIPTION", "").strip()
    profile.niche = os.getenv("CHANNEL_NICHE", "").strip()
    profile.audience = os.getenv("CHANNEL_AUDIENCE", "").strip()
    profile.language = os.getenv("CHANNEL_LANGUAGE", profile.language).strip() or profile.language
    profile.region = os.getenv("CHANNEL_REGION", profile.region).strip() or profile.region
    directive = os.getenv("CHANNEL_CREATIVE_DIRECTIVE", "").strip()
    if directive:
        brain.creative_directive.update(directive)
    return brain


def save_channel_brain(brain: Optional[ChannelBrain] = None) -> bool:
    """Persists Channel Brain to JSON file."""
    global _CHANNEL_BRAIN
    if brain is not None:
        _CHANNEL_BRAIN = brain
    if _CHANNEL_BRAIN is None:
        return False
    
    _CHANNEL_BRAIN.updated_at = datetime.utcnow().isoformat() + "Z"
    _CHANNEL_BRAIN.version += 1
    
    _BRAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_BRAIN_PATH, "w", encoding="utf-8") as f:
            json.dump(_CHANNEL_BRAIN.to_dict(), f, indent=2, ensure_ascii=False)
        log.info(f"Saved Channel Brain v{_CHANNEL_BRAIN.version} to {_BRAIN_PATH}")
        return True
    except Exception as e:
        log.error(f"Failed to save Channel Brain: {e}")
        return False


def reset_channel_brain() -> ChannelBrain:
    """Creates and saves a fresh default Channel Brain."""
    global _CHANNEL_BRAIN
    _CHANNEL_BRAIN = ChannelBrain()
    save_channel_brain()
    return _CHANNEL_BRAIN
