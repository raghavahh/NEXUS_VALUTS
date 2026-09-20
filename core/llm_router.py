"""
NEXUS VAULTS 2.0 - 100% Cloud Task-Based LLM Router
Dynamically routes requests through the AI_PROVIDER_CHAIN defined in .env.
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

    # 2. Use JSONDecoder.raw_decode scanning for valid JSON objects or arrays
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

    # 3. Fallback to outer braces
    first_brace = clean.find("{")
    last_brace = clean.rfind("}")
    if first_brace != -1 and last_brace != -1:
        candidate = clean[first_brace:last_brace + 1].strip()
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            try:
                parsed = ast.literal_eval(candidate)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed)
            except Exception:
                return candidate

    # 4. Fallback to ast.literal_eval for single-quoted Python dicts/lists
    try:
        parsed = ast.literal_eval(clean)
        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed)
    except Exception:
        pass

    return clean


def call_openrouter(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """OpenRouter Cloud API caller using configuration from .env"""
    api_key = config.ai.openrouter_api_key
    base_url = config.ai.openrouter_api_url.rstrip("/")
    if not api_key:
        return None

    models = [config.ai.openrouter_model]
    for fb in ("liquid/lfm-2.5-2.6b:free", "nvidia/nemotron-3-super-120b-a12b:free"):
        if fb not in models:
            models.append(fb)

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

    for model in models:
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

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/nexus-vaults",
                    "X-Title": "Nexus Vaults Engine"
                }
            )
            with urllib.request.urlopen(req, timeout=config.ai.request_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    log.info(f"Generated via OpenRouter ({model})")
                    return text
        except urllib.error.HTTPError as e:
            log.warning(f"OpenRouter ({model}) HTTP {e.code}: {e.reason}")
            if e.code in (401, 403):
                return None
            continue
        except Exception as e:
            log.warning(f"OpenRouter ({model}) error: {e}")
            continue
    return None

def call_groq(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """Groq Cloud API caller using configuration from .env"""
    api_key = config.ai.groq_api_key
    model = config.ai.groq_model
    base_url = config.ai.groq_api_url.rstrip("/")
    if not api_key:
        return None

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

    models_to_try = [model]
    for alt in ("qwen/qwen3.8-27b", "openai/gpt-oss-120b"):
        if alt not in models_to_try:
            models_to_try.append(alt)

    for current_model in models_to_try:
        url = f"{base_url}/chat/completions"
        payload = {
            "model": current_model,
            "messages": [
                {"role": "system", "content": system_prompt or "Documentary intelligence system."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": 6000
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            with urllib.request.urlopen(req, timeout=config.ai.request_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    log.info(f"Generated via Groq ({current_model})")
                    return text
        except urllib.error.HTTPError as e:
            log.warning(f"Groq ({current_model}) HTTP {e.code}: {e.reason}")
            if e.code in (401, 403):
                return None
            continue
        except Exception as e:
            log.warning(f"Groq ({current_model}) error: {e}")
            continue
    return None

def call_nvidia(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """NVIDIA NIM Cloud API caller using configuration from .env"""
    api_key = config.ai.nvidia_api_key
    model = config.ai.nvidia_model
    base_url = config.ai.nvidia_api_url.rstrip("/")
    if not api_key:
        return None

    # Set temperature and top_p based on task type
    if task_type in ("hooks", "script", "growth"):
        temperature = 1.0
        top_p = 0.95
    elif task_type in ("claim_verification", "storyboard_json", "seo_structure"):
        temperature = 0.2
        top_p = 0.95
    else:
        temperature = 0.6
        top_p = 0.9

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "Documentary scriptwriter and critic."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": 3000
    }

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=config.ai.request_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    log.info(f"Generated via NVIDIA NIM ({model})")
                    return text
        except urllib.error.HTTPError as e:
            log.warning(f"NVIDIA NIM ({model}) HTTP {e.code}: {e.reason}")
            if e.code in (401, 403, 404):
                break
            elif e.code == 429 and attempt < max_attempts - 1:
                import time
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 5.0
                else:
                    wait_time = 5.0
                time.sleep(wait_time)
            else:
                break
        except Exception as e:
            log.warning(f"NVIDIA NIM ({model}) error: {e}")
            break
    return None

_LAST_GEMINI_CALL = 0.0

def call_gemini(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """Google Gemini Cloud API caller using configuration from .env"""
    global _LAST_GEMINI_CALL
    api_key = config.ai.gemini_api_key
    model = config.ai.gemini_model
    base_url = config.ai.gemini_api_url.rstrip("/")
    if not api_key:
        return None

    # Defensive 2.0s call pacing to adhere strictly to Google AI Studio free-tier RPM limits
    now = time.time()
    elapsed = now - _LAST_GEMINI_CALL
    if elapsed < 2.0:
        time.sleep(2.0 - elapsed)
    _LAST_GEMINI_CALL = time.time()

    # Set temperature and top_p based on task type
    if task_type in ("hooks", "script", "growth"):
        temperature = 1.0
        top_p = 0.95
    elif task_type in ("claim_verification", "storyboard_json", "seo_structure"):
        temperature = 0.2
        top_p = 0.95
    else:
        temperature = 0.7
        top_p = 0.9  # default for other task_types

    models_to_try = [model]
    for alt in ("gemini-3.6-flash", "gemini-3.8-flash"):
        if alt not in models_to_try:
            models_to_try.append(alt)

    for current_model in models_to_try:
        url = f"{base_url}/models/{current_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}],
            "generationConfig": {"temperature": temperature, "top_p": top_p, "maxOutputTokens": 4096}
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=config.ai.request_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text:
                        log.info(f"Generated via Gemini ({current_model})")
                        return text
        except urllib.error.HTTPError as e:
            log.warning(f"Gemini ({current_model}) HTTP {e.code}: {e.reason}")
            if e.code in (401, 403):
                return None
            elif e.code == 429:
                time.sleep(3.0)
            continue
        except Exception as e:
            log.warning(f"Gemini ({current_model}) error: {e}")
            continue

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
        "Clean pipeline abort: please verify your API keys and provider models in C:\\YT-SHORTS\\.env."
    )
