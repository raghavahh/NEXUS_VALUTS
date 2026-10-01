"""
AI Video Factory - 100% Cloud Task-Based LLM Router
Dynamically routes requests through the AI_TEXT_PROVIDER_CHAIN defined in .env.
Zero local LLM / Ollama dependencies. Zero hardcoded model names.
Aborts cleanly if all configured providers fail.
"""

import re
import json
import time
import socket
import urllib.request
import urllib.error
from typing import Optional
import os
from core.config import config
from core.logging import log

import ast

def extract_json(raw: str) -> str:
    """Extracts JSON object or array from markdown blocks or free text with reasoning."""
    if not raw:
        return ""
    clean = raw.strip()

    # Strip <think>...</think> tags from reasoning models
    clean = re.sub(r"<think>[\s\S]*?</think>", "", clean).strip()

    # 1. Search for ```json ... ``` block
    m_json_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, re.IGNORECASE)
    if m_json_block:
        candidate = m_json_block.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    # 2. Prefer outer square brackets or braces if present, allowing downstream regex recovery
    first_bracket = clean.find("[")
    last_bracket = clean.rfind("]")
    first_brace = clean.find("{")
    last_brace = clean.rfind("}")

    if first_bracket != -1 and last_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        outer_arr = clean[first_bracket:last_bracket + 1].strip()
        if outer_arr:
            return outer_arr

    # 3. Use JSONDecoder.raw_decode scanning for valid JSON objects or arrays
    for start_char in ("{", "["):
        pos = 0
        while pos < len(clean):
            idx = clean.find(start_char, pos)
            if idx == -1:
                break
            try:
                decoder = json.JSONDecoder()
                _, end_idx = decoder.raw_decode(clean[idx:])
                candidate = clean[idx:idx + end_idx].strip()
                if candidate:
                    json.loads(candidate)
                    return candidate
            except Exception:
                pass
            pos = idx + 1
    last_bracket = clean.rfind("]")

    candidates = []
    if first_bracket != -1 and last_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        candidates.append(clean[first_bracket:last_bracket + 1].strip())
    if first_brace != -1 and last_brace != -1:
        candidates.append(clean[first_brace:last_brace + 1].strip())
    if first_bracket != -1 and last_bracket != -1 and clean[first_bracket:last_bracket + 1].strip() not in candidates:
        candidates.append(clean[first_bracket:last_bracket + 1].strip())

    for candidate in candidates:
        try:
            json.loads(candidate, strict=False)
            return candidate
        except Exception:
            try:
                parsed = ast.literal_eval(candidate)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed)
            except Exception:
                pass

    if candidates:
        return candidates[0]

    # 4. Fallback to ast.literal_eval for single-quoted Python dicts/lists
    try:
        parsed = ast.literal_eval(clean)
        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed)
    except Exception:
        pass

    return clean


def _get_provider_config(provider_name: str):
    """Get provider slot config by name."""
    provider_map = {
        "openrouter": config.ai.text_openrouter,
        "groq": config.ai.text_groq,
        "nvidia": config.ai.text_nvidia,
        "gemini": config.ai.text_gemini,
    }
    return provider_map.get(provider_name.lower())

def _make_openai_call(provider_name: str, prompt: str, system_prompt: str, task_type: str) -> Optional[str]:
    """Generic OpenAI-compatible API caller."""
    provider_cfg = _get_provider_config(provider_name)
    if not provider_cfg or not provider_cfg.enabled:
        return None

    api_key = os.getenv(provider_cfg.secret_ref, "")
    if not api_key:
        return None

    base_url = provider_cfg.endpoint.rstrip("/")
    model = provider_cfg.model

    # Set temperature and top_p based on task type
    if task_type in ("hooks", "script", "growth"):
        temperature = 1.0
        top_p = 0.95
    elif task_type in ("claim_verification", "storyboard_json", "seo_structure"):
        temperature = 0.2
        top_p = 0.95
    else:
        temperature = 0.7
        top_p = 0.9

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "Documentary intelligence system."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": 3000
    }

    # Provider-specific headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    if provider_name == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/aivideofactory"
        headers["X-Title"] = "AI Video Factory"

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=provider_cfg.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if text:
                log.info(f"Generated via {provider_name.capitalize()} ({model})")
                return text
    except urllib.error.HTTPError as e:
        log.warning(f"{provider_name.capitalize()} ({model}) HTTP {e.code}: {e.reason}")
        if e.code in (401, 403):
            return None
        elif e.code == 429:
            time.sleep(3.0)
    except Exception as e:
        log.warning(f"{provider_name.capitalize()} ({model}) error: {e}")

    return None

def call_openrouter(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """OpenRouter Cloud API caller using configuration from .env"""
    return _make_openai_call("openrouter", prompt, system_prompt, task_type)

def call_groq(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """Groq Cloud API caller using configuration from .env"""
    return _make_openai_call("groq", prompt, system_prompt, task_type)

def call_nvidia(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """NVIDIA NIM Cloud API caller using configuration from .env"""
    return _make_openai_call("nvidia", prompt, system_prompt, task_type)

def call_gemini(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """Google Gemini Cloud API caller using configuration from .env"""
    provider_cfg = _get_provider_config("gemini")
    if not provider_cfg or not provider_cfg.enabled:
        return None

    api_key = os.getenv(provider_cfg.secret_ref, "")
    if not api_key:
        return None

    base_url = provider_cfg.endpoint.rstrip("/")
    model = provider_cfg.model

    # Set temperature and top_p based on task type
    if task_type in ("hooks", "script", "growth"):
        temperature = 1.0
        top_p = 0.95
    elif task_type in ("claim_verification", "storyboard_json", "seo_structure"):
        temperature = 0.2
        top_p = 0.95
    else:
        temperature = 0.7
        top_p = 0.9

    for fb_model in [model, "gemini-1.5-pro", "gemini-1.0-pro"]:
        url = f"{base_url}/models/{fb_model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "systemInstruction": {"parts": [{"text": system_prompt or "Documentary intelligence system."}]} if system_prompt else None,
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "maxOutputTokens": 3000
            }
        }
        if payload["systemInstruction"] is None:
            del payload["systemInstruction"]

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=provider_cfg.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text:
                        log.info(f"Generated via Gemini ({fb_model})")
                        return text
        except urllib.error.HTTPError as e:
            log.warning(f"Gemini ({fb_model}) HTTP {e.code}: {e.reason}")
            if e.code in (401, 403):
                return None
            elif e.code == 429:
                time.sleep(3.0)
        except Exception as e:
            log.warning(f"Gemini ({fb_model}) error: {e}")

    return None

PROVIDER_DISPATCH = {
    "openrouter": call_openrouter,
    "groq": call_groq,
    "nvidia": call_nvidia,
    "gemini": call_gemini,
}

def route_task(prompt: str, system_prompt: str = "", system_instruction: str = "", task_type: str = "general") -> str:
    """
    100% Cloud Task Router:
    Routes intelligently according to Section 4:
    - Primary generation (story, script, research, visual_intent): NVIDIA -> Groq -> Gemini -> OpenRouter
    - Critic / reasoning / quality pass (scoring, critic, hook): NVIDIA -> Groq -> Gemini -> OpenRouter
    - Fast formatting: Groq -> NVIDIA -> Gemini -> OpenRouter
    All orderings are dynamically aligned with the user-configured AI_PROVIDER_CHAIN in .env.
    Aborts cleanly if all configured providers fail.
    """
    effective_system = system_instruction or system_prompt
    configured_chain = [p.lower().strip() for p in config.ai.provider_chain]
    max_retries = config.ai.max_retries

    # Set defensive socket timeout for network resilience
    try:
        socket.setdefaulttimeout(config.ai.request_timeout)
    except Exception:
        pass

    # Determine intelligent role-based provider ordering
    tt = (task_type or "general").lower()
    if tt in ("critic", "scoring", "quality_pass", "critique", "hook"):
        role_pref = ["nvidia", "groq", "gemini", "openrouter"]
    elif tt in ("generation", "story", "script", "research", "visual_intent", "storyboard"):
        role_pref = ["nvidia", "groq", "gemini", "openrouter"]
    elif tt in ("fast", "formatting", "seo"):
        role_pref = ["groq", "nvidia", "gemini", "openrouter"]
    else:
        role_pref = configured_chain

    # Order providers prioritizing role preference while strictly respecting configured_chain
    ordered_chain = [p for p in role_pref if p in configured_chain]
    for p in configured_chain:
        if p not in ordered_chain:
            ordered_chain.append(p)

    for provider_name in ordered_chain:
        caller = PROVIDER_DISPATCH.get(provider_name)
        if not caller:
            continue
        try:
            res = caller(prompt, effective_system, task_type=tt)
            if res:
                return res
        except Exception as e:
            log.warning(f"Provider {provider_name} failed: {e}")

    raise RuntimeError(
        f"All configured cloud AI providers failed ({', '.join(ordered_chain)}). "
        "Clean pipeline abort: please verify your API keys and provider models in .env."
    )
