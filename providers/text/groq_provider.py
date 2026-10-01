"""
AI Video Factory - Groq Text Provider
"""

import json
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from providers.text import TextProvider, TextGenerationRequest, TextGenerationResult
from core.config import config
from core.logging import log


class GroqTextProvider(TextProvider):
    """Groq text generation provider."""
    
    def __init__(self, slot):
        super().__init__(slot)
        self.api_key = ""
        self.api_url = slot.endpoint or "https://api.groq.com/openai/v1"
        self._load_credentials()
    
    def _load_credentials(self):
        import os
        self.api_key = os.getenv(self.slot.secret_ref, "")
    
    def validate_config(self) -> bool:
        return bool(self.api_key)
    
    def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        if not self.validate_config():
            raise RuntimeError("Groq API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        
        payload = {
            "model": self.model or "qwen/qwen3.8-27b",
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        
        url = f"{self.api_url}/chat/completions"
        
        for attempt in range(self.slot.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.slot.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices:
                        text = choices[0].get("message", {}).get("content", "")
                        if text:
                            log.info(f"Generated via Groq ({self.model})")
                            return TextGenerationResult(
                                text=text,
                                provider="groq",
                                model=self.model,
                                usage=data.get("usage", {}),
                                metadata={"attempt": attempt + 1}
                            )
            except urllib.error.HTTPError as e:
                log.warning(f"Groq HTTP {e.code}: {e.reason}")
                if e.code in (401, 403):
                    raise RuntimeError("Groq authentication failed")
                elif e.code == 429:
                    time.sleep(3.0)
                else:
                    if attempt == self.slot.max_retries:
                        raise
            except Exception as e:
                log.warning(f"Groq error: {e}")
                if attempt == self.slot.max_retries:
                    raise
        
        raise RuntimeError("Groq generation failed after retries")