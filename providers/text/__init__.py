"""
AI Video Factory - Text Provider Abstraction
Generic text generation provider interface with capability model.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class ProviderCapability(Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class ProviderSlot:
    """Configuration for a single provider slot (Primary/Backup1/Backup2)."""
    enabled: bool = True
    provider: str = ""  # e.g., "nvidia", "groq", "gemini", "openrouter"
    model: str = ""
    endpoint: str = ""
    secret_ref: str = ""  # e.g., "NVIDIA_API_KEY", "GEMINI_API_KEY"
    timeout: int = 30
    max_retries: int = 1
    capabilities: List[ProviderCapability] = field(default_factory=lambda: [ProviderCapability.TEXT])


@dataclass
class TextGenerationRequest:
    """Normalized text generation request."""
    prompt: str
    system_prompt: str = ""
    task_type: str = "general"
    temperature: float = 0.7
    max_tokens: int = 4000
    response_format: str = "text"  # "text" | "json"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextGenerationResult:
    """Normalized text generation result."""
    text: str
    provider: str
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TextProvider:
    """Base class for text generation providers."""
    
    def __init__(self, slot: ProviderSlot):
        self.slot = slot
        self.name = slot.provider
        self.model = slot.model
    
    def supports_capability(self, capability: ProviderCapability) -> bool:
        return capability in self.slot.capabilities
    
    def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        raise NotImplementedError("Subclasses must implement generate()")
    
    def validate_config(self) -> bool:
        """Validates that required configuration is present."""
        if not self.slot.secret_ref:
            return False
        import os
        return bool(os.getenv(self.slot.secret_ref))


def create_text_provider(slot: ProviderSlot) -> Optional[TextProvider]:
    """Factory function to create text provider instances."""
    provider_name = slot.provider.lower()
    
    if provider_name == "nvidia":
        from providers.text.nvidia_provider import NvidiaTextProvider
        return NvidiaTextProvider(slot)
    elif provider_name == "groq":
        from providers.text.groq_provider import GroqTextProvider
        return GroqTextProvider(slot)
    elif provider_name == "gemini":
        from providers.text.gemini_provider import GeminiTextProvider
        return GeminiTextProvider(slot)
    elif provider_name == "openrouter":
        from providers.text.openrouter_provider import OpenRouterTextProvider
        return OpenRouterTextProvider(slot)
    
    return None


def get_text_provider_chain(config_obj) -> List[TextProvider]:
    """Builds the text provider chain from configuration."""
    providers = []
    chain = getattr(config_obj.ai, "provider_chain", ["nvidia", "groq", "gemini", "openrouter"])
    
    for i, provider_name in enumerate(chain):
        slot_name = f"text_{provider_name}"
        if hasattr(config_obj.ai, slot_name):
            slot = getattr(config_obj.ai, slot_name)
            if slot.enabled:
                provider = create_text_provider(slot)
                if provider and provider.validate_config():
                    providers.append(provider)
    
    # Fallback: create default slots if none configured
    if not providers:
        for provider_name in chain:
            slot = ProviderSlot(
                enabled=True,
                provider=provider_name,
                model=getattr(config_obj.ai, f"{provider_name}_model", ""),
                endpoint=getattr(config_obj.ai, f"{provider_name}_api_url", ""),
                secret_ref=f"{provider_name.upper()}_API_KEY",
                timeout=config_obj.ai.request_timeout,
                max_retries=config_obj.ai.max_retries,
            )
            provider = create_text_provider(slot)
            if provider and provider.validate_config():
                providers.append(provider)
    
    return providers