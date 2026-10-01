"""
AI Video Factory - Video Provider Abstraction
Generic video generation provider interface with capability model and async job support.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from providers.text import ProviderCapability


class VideoJobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VideoProviderSlot:
    """Configuration for a single video provider slot (Primary/Backup1/Backup2)."""
    enabled: bool = True
    provider: str = ""  # e.g., "runway", "pika", "luma", "kling"
    model: str = ""
    endpoint: str = ""
    secret_ref: str = ""  # e.g., "RUNWAY_API_KEY", "PIKA_API_KEY"
    timeout: int = 300  # 5 minutes for video generation
    max_retries: int = 1
    capabilities: List[ProviderCapability] = field(default_factory=lambda: [ProviderCapability.VIDEO])
    supports_audio: bool = False
    async_mode: bool = True  # Most video APIs are async


@dataclass
class VideoGenerationRequest:
    """Normalized video generation request."""
    prompt: str
    duration: float  # seconds
    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    fps: int = 30
    references: List[str] = field(default_factory=list)  # Reference image/video URLs
    audio_requested: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoGenerationResult:
    """Normalized video generation result."""
    media_path: str  # Local path to generated video
    has_audio: bool
    duration: float
    provider: str
    model: str
    job_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class VideoProvider:
    """Base class for video generation providers."""
    
    def __init__(self, slot: VideoProviderSlot):
        self.slot = slot
        self.name = slot.provider
        self.model = slot.model
    
    def supports_capability(self, capability: ProviderCapability) -> bool:
        return capability in self.slot.capabilities
    
    def supports_audio_generation(self) -> bool:
        return self.slot.supports_audio
    
    def submit_job(self, request: VideoGenerationRequest) -> str:
        """
        Submits a video generation job.
        Returns a job ID for polling.
        """
        raise NotImplementedError("Subclasses must implement submit_job()")
    
    def poll_job(self, job_id: str) -> VideoJobStatus:
        """
        Polls the job status.
        Returns the current status.
        """
        raise NotImplementedError("Subclasses must implement poll_job()")
    
    def retrieve_result(self, job_id: str) -> VideoGenerationResult:
        """
        Retrieves the completed video result.
        Returns a VideoGenerationResult with local media path.
        """
        raise NotImplementedError("Subclasses must implement retrieve_result()")
    
    def generate_sync(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """
        Synchronous generation (for providers that support it).
        Default implementation uses async submit/poll/retrieve.
        """
        job_id = self.submit_job(request)
        while True:
            status = self.poll_job(job_id)
            if status == VideoJobStatus.COMPLETED:
                return self.retrieve_result(job_id)
            elif status == VideoJobStatus.FAILED:
                raise RuntimeError(f"Video generation job {job_id} failed")
            import time
            time.sleep(5)
    
    def validate_config(self) -> bool:
        """Validates that required configuration is present."""
        if not self.slot.secret_ref:
            return False
        import os
        return bool(os.getenv(self.slot.secret_ref))


def create_video_provider(slot: VideoProviderSlot) -> Optional[VideoProvider]:
    """Factory function to create video provider instances."""
    provider_name = slot.provider.lower()
    
    if provider_name == "runway":
        from providers.video.runway_provider import RunwayVideoProvider
        return RunwayVideoProvider(slot)
    elif provider_name == "pika":
        try:
            from providers.video.pika_provider import PikaVideoProvider
            return PikaVideoProvider(slot)
        except ModuleNotFoundError:
            return None
    elif provider_name == "luma":
        try:
            from providers.video.luma_provider import LumaVideoProvider
            return LumaVideoProvider(slot)
        except ModuleNotFoundError:
            return None
    elif provider_name == "kling":
        try:
            from providers.video.kling_provider import KlingVideoProvider
            return KlingVideoProvider(slot)
        except ModuleNotFoundError:
            return None
    
    return None


def get_video_provider_chain(config_obj) -> List[VideoProvider]:
    """Builds the video provider chain from configuration."""
    providers = []
    # Video provider chain is configured separately
    chain = getattr(config_obj.ai, "video_provider_chain", ["runway", "pika", "luma"])
    
    for provider_name in chain:
        slot_name = f"video_{provider_name}"
        if hasattr(config_obj.ai, slot_name):
            slot = getattr(config_obj.ai, slot_name)
            if slot.enabled:
                provider = create_video_provider(slot)
                if provider and provider.validate_config():
                    providers.append(provider)
    
    return providers
