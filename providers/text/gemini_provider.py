"""
AI Video Factory - Gemini Text Provider
"""

import json
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from providers.text import TextProvider, TextGenerationRequest, TextGenerationResult
from core.config import config
from core.logging import log


class GeminiTextProvider(TextProvider):
    """Google Gemini text generation provider."""
    
    def __init__(self, slot):
        super().__init__(slot)
        self.api_key = ""
        self.api_url = slot.endpoint or "https://generativelanguage.googleapis.com/v1beta"
        self._load_credentials()
    
    def _load_credentials(self):
        import os
        self.api_key = os.getenv(self.slot.secret_ref, "")
    
    def validate_config(self) -> bool:
        return bool(self.api_key)
    
    def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        if not self.validate_config():
            raise RuntimeError("Gemini API key not configured")
        
        # Combine system prompt and user prompt for Gemini
        combined_prompt = ""
        if request.system_prompt:
            combined_prompt = f"{request.system_prompt}\n\n"
        combined_prompt += request.prompt
        
        payload = {
            "contents": [
                {
                    "parts": [{"text": combined_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            }
        }
        
        if request.response_format == "json":
            payload["generationConfig"]["responseMimeType"] = "application/json"
        
        url = f"{self.api_url}/models/{self.model or 'gemini-1.5-flash'}:generateContent?key={self.api_key}"
        
        for attempt in range(self.slot.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.slot.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            text = parts[0].get("text", "")
                            if text:
                                log.info(f"Generated via Gemini ({self.model})")
                                return TextGenerationResult(
                                    text=text,
                                    provider="gemini",
                                    model=self.model,
                                    usage=data.get("usageMetadata", {}),
                                    metadata={"attempt": attempt + 1}
                                )
            except urllib.error.HTTPError as e:
                log.warning(f"Gemini HTTP {e.code}: {e.reason}")
                if e.code in (401, 403):
                    raise RuntimeError("Gemini authentication failed")
                elif e.code == 429:
                    time.sleep(3.0)
                else:
                    if attempt == self.slot.max_retries:
                        raise
            except Exception as e:
                log.warning(f"Gemini error: {e}")
                if attempt == self.slot.max_retries:
                    raise
        
        raise RuntimeError("Gemini generation failed after retries")