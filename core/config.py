"""
NEXUS VAULTS 2.0 - Centralized Configuration Layer
Single Source of Truth: C:\\YT-SHORTS\\.env
Loads runtime configuration into typed, immutable configuration objects.
Strictly masks credentials in logs and diagnostics.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# Project Root Directory
BASE_DIR = Path(__file__).resolve().parent.parent

def load_dotenv():
    """
    Loads C:\\YT-SHORTS\\.env into os.environ.
    Preserves existing environment values if already set (e.g. in CI).
    TEST FIREWALL: when NEXUS_TEST_SANDBOX is set (tests/_guard.py), the
    production .env is NEVER loaded — tests run with blanked credentials only.
    """
    if os.getenv("NEXUS_TEST_SANDBOX"):
        return
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and not os.getenv(k):
                            os.environ[k] = v
        except Exception:
            pass

# Load environment on module import
load_dotenv()

def _safe_relpath(p) -> str:
    """Relative to BASE_DIR when possible (sandbox temp dirs live elsewhere)."""
    try:
        return str(p.relative_to(BASE_DIR))
    except ValueError:
        return str(p)

def _mask_secret(val: Optional[str]) -> str:
    """Safely reports credential presence as SET or NOT SET without exposing any fragment."""
    if not val or not str(val).strip():
        return "NOT SET"
    return "SET"

def _clean_str(val: Optional[str], default: str = "") -> str:
    if val is None:
        return default
    v = str(val).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v or default

def _parse_bool(val: str, default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "on")

@dataclass(frozen=True)
class AppConfig:
    env: str = os.getenv("APP_ENV", "development")
    mode: str = os.getenv("APP_MODE", "test")
    debug: bool = _parse_bool(os.getenv("DEBUG", "false"), False)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

@dataclass(frozen=True)
class AIConfig:
    provider_chain: List[str] = field(default_factory=lambda: [
        p.strip() for p in os.getenv("AI_PROVIDER_CHAIN", "nvidia,groq,gemini,openrouter").split(",") if p.strip()
    ])
    request_timeout: int = int(os.getenv("AI_REQUEST_TIMEOUT", "30"))
    max_retries: int = int(os.getenv("AI_MAX_RETRIES", "1"))

    gemini_api_key: str = _clean_str(os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = _clean_str(os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    gemini_api_url: str = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta")

    nvidia_api_key: str = _clean_str(os.getenv("NVIDIA_API_KEY", ""))
    nvidia_model: str = _clean_str(os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"))
    nvidia_api_url: str = os.getenv("NVIDIA_API_URL", "https://integrate.api.nvidia.com/v1")

    groq_api_key: str = _clean_str(os.getenv("GROQ_API_KEY", ""))
    groq_model: str = _clean_str(os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"))
    groq_api_url: str = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1")

    openrouter_api_key: str = _clean_str(os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model: str = _clean_str(os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"))
    openrouter_api_url: str = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")

@dataclass(frozen=True)
class YouTubeConfig:
    client_id: str = _clean_str(os.getenv("YT_CLIENT_ID", ""))
    client_secret: str = _clean_str(os.getenv("YT_CLIENT_SECRET", ""))
    refresh_token: str = _clean_str(os.getenv("YT_REFRESH_TOKEN", ""))
    category_id: str = os.getenv("YOUTUBE_CATEGORY_ID", "28")
    default_language: str = os.getenv("YOUTUBE_DEFAULT_LANGUAGE", "en")
    upload_privacy: str = os.getenv("YOUTUBE_UPLOAD_PRIVACY", "private")
    channel_name: str = "NEXUS VAULTS"
    handle: str = "@NEXUS_VAULTS"
    DAILY_QUOTA_LIMIT: int = 10000
    VIDEO_INSERT_COST: int = 1600

@dataclass(frozen=True)
class MediaConfig:
    pexels_api_key: str = os.getenv("PEXELS_API_KEY", "")

    @property
    def pexels_enabled(self) -> bool:
        return bool(self.pexels_api_key and self.pexels_api_key.strip())

@dataclass(frozen=True)
class ResearchConfig:
    max_topics: int = int(os.getenv("RESEARCH_MAX_TOPICS", "5"))
    max_candidates: int = int(os.getenv("RESEARCH_MAX_CANDIDATES", "3"))
    content_pillars: List[str] = field(default_factory=lambda: [
        p.strip() for p in os.getenv(
            "RESEARCH_CONTENT_PILLARS",
            "Classified History,Unexplained Events,Scientific Mysteries,Strange Real Events"
        ).split(",") if p.strip()
    ])

@dataclass(frozen=True)
class StoryConfig:
    target_duration: float = float(os.getenv("STORY_TARGET_DURATION", "36"))
    min_duration: float = float(os.getenv("STORY_MIN_DURATION", "30"))
    max_duration: float = float(os.getenv("STORY_MAX_DURATION", "40"))
    min_words: int = int(os.getenv("STORY_MIN_WORDS", "68"))
    max_words: int = int(os.getenv("STORY_MAX_WORDS", "84"))

@dataclass(frozen=True)
class HookConfig:
    candidate_count: int = int(os.getenv("HOOK_CANDIDATE_COUNT", "10"))
    min_score: float = float(os.getenv("HOOK_MIN_SCORE", "0.75"))

@dataclass(frozen=True)
class SceneConfig:
    min_count: int = int(os.getenv("SCENE_MIN_COUNT", "10"))
    target_count: int = int(os.getenv("SCENE_TARGET_COUNT", "12"))
    max_count: int = int(os.getenv("SCENE_MAX_COUNT", "15"))
    min_duration: float = float(os.getenv("SCENE_MIN_DURATION", "2.0"))
    max_duration: float = float(os.getenv("SCENE_MAX_DURATION", "4.5"))
    # Unified dedup threshold — one .env key: DEDUP_HAMMING_THRESHOLD
    # IMAGE_DEDUP_HAMMING_THRESHOLD is a legacy alias kept for backward compatibility only.
    dedup_hamming_threshold: int = int(os.getenv("DEDUP_HAMMING_THRESHOLD", os.getenv("IMAGE_DEDUP_HAMMING_THRESHOLD", "6")))
    dedup_sha_enabled: bool = _parse_bool(os.getenv("DEDUP_SHA_ENABLED", "true"), True)
    relevance_min_score: float = float(os.getenv("SCENE_RELEVANCE_MIN_SCORE", "0.60"))
    adaptive_style: bool = _parse_bool(os.getenv("STYLE_TREATMENT_ADAPTIVE", "true"), True)
    max_candidates_per_scene: int = int(os.getenv("IMAGE_MAX_CANDIDATES_PER_SCENE", "3"))
    max_generated_graphics: int = int(os.getenv("SCENE_MAX_GENERATED_GRAPHICS", "3"))
    min_authentic_assets: int = int(os.getenv("SCENE_MIN_AUTHENTIC_ASSETS", "4"))

@dataclass(frozen=True)
class RenderConfig:
    width: int = int(os.getenv("RENDER_WIDTH", "1080"))
    height: int = int(os.getenv("RENDER_HEIGHT", "1920"))
    fps: int = int(os.getenv("RENDER_FPS", "30"))
    codec: str = os.getenv("RENDER_CODEC", "libx264")
    crf: str = os.getenv("RENDER_CRF", "20")
    preset: str = os.getenv("RENDER_PRESET", "fast")
    audio_codec: str = os.getenv("RENDER_AUDIO_CODEC", "aac")
    audio_bitrate: str = os.getenv("RENDER_AUDIO_BITRATE", "192k")
    pixel_format: str = os.getenv("RENDER_PIXEL_FORMAT", "yuv420p")

@dataclass(frozen=True)
class AudioConfig:
    voice: str = os.getenv("AUDIO_VOICE", "en-US-ChristopherNeural")
    rate: str = os.getenv("AUDIO_RATE", "+4%")
    pitch: str = os.getenv("AUDIO_PITCH", "-2Hz")
    voice_volume: float = float(os.getenv("AUDIO_VOICE_VOLUME", "-3.0"))
    background_volume: float = float(os.getenv("AUDIO_BACKGROUND_VOLUME", "-28.0"))
    ducking_attenuation_db: float = float(os.getenv("AUDIO_DUCKING_ATTENUATION_DB", "-26.0"))
    loudnorm_i: float = float(os.getenv("AUDIO_LOUDNORM_I", "-14.0"))
    loudnorm_tp: float = float(os.getenv("AUDIO_LOUDNORM_TP", "-1.5"))
    loudnorm_lra: float = float(os.getenv("AUDIO_LOUDNORM_LRA", "11.0"))
    transition_sfx_enabled: bool = _parse_bool(os.getenv("AUDIO_TRANSITION_SFX_ENABLED", "true"), True)

@dataclass(frozen=True)
class CaptionConfig:
    font: str = os.getenv("CAPTION_FONT", "Arial Black")
    font_size: int = int(os.getenv("CAPTION_FONT_SIZE", "68"))
    words_per_line: int = int(os.getenv("CAPTION_WORDS_PER_LINE", "4"))

@dataclass(frozen=True)
class SEOConfig:
    title_max_length: int = int(os.getenv("SEO_TITLE_MAX_LENGTH", "58"))
    description_max_length: int = int(os.getenv("SEO_DESCRIPTION_MAX_LENGTH", "500"))
    tag_max_count: int = int(os.getenv("SEO_TAG_MAX_COUNT", "10"))

@dataclass(frozen=True)
class QCConfig:
    min_duration: float = float(os.getenv("QC_MIN_DURATION", "30.0"))
    max_duration: float = float(os.getenv("QC_MAX_DURATION", "40.0"))
    min_scenes: int = int(os.getenv("QC_MIN_SCENES", "10"))
    max_scenes: int = int(os.getenv("QC_MAX_SCENES", "15"))
    require_unique_assets: bool = _parse_bool(os.getenv("QC_REQUIRE_UNIQUE_ASSETS", "true"), True)
    require_frame_verification: bool = _parse_bool(os.getenv("QC_REQUIRE_FRAME_VERIFICATION", "true"), True)
    frame_sample_offset: float = float(os.getenv("QC_FRAME_SAMPLE_OFFSET", "0.5"))
    frame_match_threshold: float = float(os.getenv("QC_FRAME_MATCH_THRESHOLD", "0.40"))
    sample_points_per_scene: int = int(os.getenv("QC_SAMPLE_POINTS_PER_SCENE", "3"))
    duration_tolerance: float = float(os.getenv("QC_DURATION_TOLERANCE", "0.5"))

@dataclass(frozen=True)
class StorageConfig:
    base_dir: Path = BASE_DIR
    temp_dir: Path = BASE_DIR / os.getenv("TEMP_DIR", "OUTPUT/temp")
    output_dir: Path = BASE_DIR / os.getenv("OUTPUT_DIR", "OUTPUT")
    storyboard_dir: Path = BASE_DIR / os.getenv("STORYBOARD_DIR", "OUTPUT/storyboard")
    database_path: Path = BASE_DIR / os.getenv("DATABASE_PATH", "nexus.db")
    cleanup_temp: bool = _parse_bool(os.getenv("STORAGE_CLEANUP_TEMP", "true"), True)
    keep_final_output: bool = _parse_bool(os.getenv("STORAGE_KEEP_FINAL_OUTPUT", "true"), True)

    @property
    def db_path(self) -> Path:
        return self.database_path

@dataclass(frozen=True)
class ScheduleConfig:
    timezone: str = os.getenv("SCHEDULE_TIMEZONE") or os.getenv("SCHEDULE_TZ", "America/New_York")
    upload_hour: int = int(os.getenv("SCHEDULE_UPLOAD_HOUR", "19"))
    upload_minute: int = int(os.getenv("SCHEDULE_UPLOAD_MINUTE", "0"))
    ready_buffer_minutes: int = int(os.getenv("SCHEDULE_READY_BUFFER_MINUTES", "60"))
    min_upload_gap_hours: int = int(os.getenv("MIN_UPLOAD_GAP_HOURS", "18"))

@dataclass(frozen=True)
class TestConfig:
    test_mode: bool = _parse_bool(os.getenv("TEST_MODE", "false"), False)
    dry_run: bool = _parse_bool(os.getenv("TEST_DRY_RUN", "false"), False)
    skip_upload: bool = _parse_bool(os.getenv("TEST_SKIP_UPLOAD", "false"), False)
    keep_artifacts: bool = _parse_bool(os.getenv("TEST_KEEP_ARTIFACTS", "false"), False)
    force_topic: Optional[str] = os.getenv("TEST_FORCE_TOPIC") or None

@dataclass(frozen=True)
class AnalyticsConfig:
    """
    Configurable heuristics for the self-learning feedback loop.
    These are bootstrap defaults — recalibrate once ANALYTICS_MIN_SAMPLE_COUNT is reached.
    """
    # Performance score formula weights (must sum to 1.0)
    score_weight_hook: float = float(os.getenv("ANALYTICS_SCORE_WEIGHT_HOOK", "0.35"))
    score_weight_retention: float = float(os.getenv("ANALYTICS_SCORE_WEIGHT_RETENTION", "0.35"))
    score_weight_engagement: float = float(os.getenv("ANALYTICS_SCORE_WEIGHT_ENGAGEMENT", "0.15"))
    score_weight_subs: float = float(os.getenv("ANALYTICS_SCORE_WEIGHT_SUBS", "0.15"))
    # Minimum observations before weight changes are committed (bootstrap guard)
    min_sample_count: int = int(os.getenv("ANALYTICS_MIN_SAMPLE_COUNT", "3"))
    # Only use analytics within this window for weight calculations
    observation_window_days: int = int(os.getenv("ANALYTICS_OBSERVATION_WINDOW_DAYS", "90"))

@dataclass(frozen=True)
class Config:
    app: AppConfig = field(default_factory=AppConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    story: StoryConfig = field(default_factory=StoryConfig)
    hook: HookConfig = field(default_factory=HookConfig)
    scene: SceneConfig = field(default_factory=SceneConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    caption: CaptionConfig = field(default_factory=CaptionConfig)
    seo: SEOConfig = field(default_factory=SEOConfig)
    qc: QCConfig = field(default_factory=QCConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    test: TestConfig = field(default_factory=TestConfig)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)

    def mask_summary(self) -> str:
        """Returns a safe, masked configuration diagnostic."""
        lines = [
            "============================================================",
            "        NEXUS VAULTS 2.0 - RUNTIME CONFIGURATION AUDIT      ",
            "============================================================",
            f"APP_ENV:            {self.app.env} (MODE: {self.app.mode})",
            f"SCHEDULE_TZ:        {self.schedule.timezone} [UPLOAD: {self.schedule.upload_hour:02d}:{self.schedule.upload_minute:02d} | READY-BY: -{self.schedule.ready_buffer_minutes}m]",
            f"AI_PROVIDER_CHAIN:  {', '.join(self.ai.provider_chain)}",
            f"OPENROUTER_KEY:     {_mask_secret(self.ai.openrouter_api_key)} [MODEL: {self.ai.openrouter_model}]",
            f"GROQ_KEY:           {_mask_secret(self.ai.groq_api_key)} [MODEL: {self.ai.groq_model}]",
            f"NVIDIA_KEY:         {_mask_secret(self.ai.nvidia_api_key)} [MODEL: {self.ai.nvidia_model}]",
            f"GEMINI_KEY:         {_mask_secret(self.ai.gemini_api_key)} [MODEL: {self.ai.gemini_model}]",
            f"YT_CLIENT_ID:       {_mask_secret(self.youtube.client_id)}",
            f"YT_CLIENT_SECRET:   {_mask_secret(self.youtube.client_secret)}",
            f"YT_REFRESH_TOKEN:   {_mask_secret(self.youtube.refresh_token)}",
            f"PEXELS STATUS:      {'ENABLED' if self.media.pexels_enabled else 'DISABLED (KEY NOT SET)'}",
            f"TARGET DURATION:    {self.story.target_duration}s ({self.story.min_duration}s - {self.story.max_duration}s)",
            f"SCENE TARGET:       {self.scene.target_count} scenes ({self.scene.min_count} - {self.scene.max_count})",
            f"RENDER SPECS:       {self.render.width}x{self.render.height} @ {self.render.fps}fps [{self.render.codec}]",
            f"STORAGE DIRS:       OUTPUT: {self.storage.output_dir.name} | TEMP: {_safe_relpath(self.storage.temp_dir)}",
            f"TEST_MODE:          {self.test.test_mode} (SKIP_UPLOAD: {self.test.skip_upload})",
            "============================================================"
        ]
        return "\n".join(lines)

    def validate(self):
        """Fail-fast validation for critical runtime parameters."""
        self.storage.output_dir.mkdir(parents=True, exist_ok=True)
        self.storage.temp_dir.mkdir(parents=True, exist_ok=True)
        self.storage.storyboard_dir.mkdir(parents=True, exist_ok=True)

        # Confirm at least one AI provider has an API key
        has_ai_key = any([
            self.ai.openrouter_api_key,
            self.ai.groq_api_key,
            self.ai.nvidia_api_key,
            self.ai.gemini_api_key
        ])
        if not has_ai_key:
            raise ValueError(
                "CRITICAL: No AI provider API key found in .env! "
                "Please configure at least one of: OPENROUTER_API_KEY, GROQ_API_KEY, "
                "NVIDIA_API_KEY, GEMINI_API_KEY."
            )

# Global configuration instance
config = Config()

# Direct convenience exports
OUTPUT_DIR = config.storage.output_dir
DB_PATH = config.storage.database_path

# Backward compatibility wrappers
class _LegacyRules:
    @property
    def min_duration_sec(self): return config.story.min_duration
    @property
    def max_duration_sec(self): return config.story.max_duration
    @property
    def target_duration_sec(self): return config.story.target_duration
    @property
    def min_scenes(self): return config.scene.min_count
    @property
    def max_scenes(self): return config.scene.max_count
    @property
    def target_words(self): return int((config.story.min_words + config.story.max_words) / 2)
    @property
    def min_words(self): return config.story.min_words
    @property
    def max_words(self): return config.story.max_words
    @property
    def width(self): return config.render.width
    @property
    def height(self): return config.render.height
    @property
    def fps(self): return config.render.fps
    @property
    def voice_primary(self): return config.audio.voice
    @property
    def voice_rate(self): return config.audio.rate
    @property
    def voice_pitch(self): return config.audio.pitch
    @property
    def voice_volume_db(self): return config.audio.voice_volume
    @property
    def ambient_volume_db(self): return config.audio.background_volume

class _LegacyChannel:
    @property
    def name(self): return config.youtube.channel_name
    @property
    def handle(self): return config.youtube.handle
    @property
    def category_id(self): return config.youtube.category_id
    @property
    def video_language(self): return config.youtube.default_language
    @property
    def privacy_status(self): return config.youtube.upload_privacy
    @property
    def DAILY_QUOTA_LIMIT(self): return config.youtube.DAILY_QUOTA_LIMIT
    @property
    def VIDEO_INSERT_COST(self): return config.youtube.VIDEO_INSERT_COST

class _LegacyAIConfig:
    @property
    def gemini_api_key(self): return config.ai.gemini_api_key
    @property
    def nvidia_api_key(self): return config.ai.nvidia_api_key
    @property
    def groq_api_key(self): return config.ai.groq_api_key
    @property
    def openrouter_api_key(self): return config.ai.openrouter_api_key

class _LegacyMediaAPIs:
    @property
    def pexels_api_key(self): return config.media.pexels_api_key

RULES = _LegacyRules()
CHANNEL = _LegacyChannel()
AI_CONFIG = _LegacyAIConfig()
MEDIA_APIS = _LegacyMediaAPIs()
