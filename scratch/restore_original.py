import sys

file_path = 'c:/YT-SHORTS/core/llm_router.py'

# Original function bodies as strings (from early reads, before modifications)
original_openrouter = '''def call_openrouter(prompt: str, system_prompt: str = "") -> Optional[str]:
    """OpenRouter Cloud API caller using configuration from .env"""
    api_key = config.ai.openrouter_api_key
    model = config.ai.openrouter_model
    base_url = config.ai.openrouter_api_url.rstrip("/")
    if not api_key:
        return None

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "Documentary intelligence system."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
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
    except Exception as e:
        log.warning(f"OpenRouter ({model}) error: {e}")
    return None
'''

original_groq = '''def call_groq(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Groq Cloud API caller using configuration from .env"""
    api_key = config.ai.groq_api_key
    model = config.ai.groq_model
    base_url = config.ai.groq_api_url.rstrip("/")
    if not api_key:
        return None

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "Documentary intelligence system."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 6000
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "NexusVaultsEngine/2.0"
            }
        )
        with urllib.request.urlopen(req, timeout=config.ai.request_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if text:
                log.info(f"Generated via Groq ({model})")
                return text
    except urllib.error.HTTPError as e:
        log.warning(f"Groq ({model}) HTTP {e.code}: {e.reason}")
        if e.code == 429:
            import time
            time.sleep(5.0)
    except Exception as e:
        log.warning(f"Groq ({model}) error: {e}")
    return None
'''

original_nvidia = '''def call_nvidia(prompt: str, system_prompt: str = "") -> Optional[str]:
    """NVIDIA NIM Cloud API caller using configuration from .env"""
    api_key = config.ai.nvidia_api_key
    model = config.ai.nvidia_model
    base_url = config.ai.nvidia_api_url.rstrip("/")
    if not api_key:
        return None

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "Documentary scriptwriter and critic."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6,
        "max_tokens": 3000
    }

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
    except Exception as e:
        log.warning(f"NVIDIA NIM ({model}) error: {e}")
    return None
'''

original_gemini = '''def call_gemini(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Google Gemini Cloud API caller using configuration from .env"""
    api_key = config.ai.gemini_api_key
    model = config.ai.gemini_model
    base_url = config.ai.gemini_api_url.rstrip("/")
    if not api_key:
        return None

    models_to_try = [model]
    for alt in ("gemini-3.5-flash", "gemini-3.8-flash", "gemini-3-flash-preview"):
        if alt not in models_to_try:
            models_to_try.append(alt)

    for current_model in models_to_try:
        url = f"{base_url}/models/{current_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\\n\\n{prompt}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
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
            if e.code == 429:
                import time
                time.sleep(1.5)
        except Exception as e:
            log.warning(f"Gemini ({current_model}) error: {e}")
    return None
'''

# Read the file
with open(file_path, 'r') as f:
    lines = f.readlines()

# We'll replace each function by finding its start and end.
# We'll do simple replacement by scanning for the function definition and then replacing until the next function definition or end of file.
# We'll do it for each function.

def replace_function(lines, func_name, new_func_text):
    # Find the line index where the function starts
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {func_name}"):
            start_idx = i
            break
    if start_idx is None:
        print(f"Could not find start of {func_name}")
        return lines
    # Find the end: look for the next line that starts with "def " (and not inside the function)
    end_idx = None
    for i in range(start_idx + 1, len(lines)):
        if lines[i].strip().startswith("def "):
            end_idx = i
            break
    if end_idx is None:
        # If no next function, replace until the end
        end_idx = len(lines)
    # Replace lines[start_idx:end_idx] with the new function lines
    new_lines = new_func_text.splitlines(keepends=True)
    return lines[:start_idx] + new_lines + lines[end_idx:]

# Replace each function
lines = replace_function(lines, "call_openrouter", original_openrouter)
lines = replace_function(lines, "call_groq", original_groq)
lines = replace_function(lines, "call_nvidia", original_nvidia)
lines = replace_function(lines, "call_gemini", original_gemini)

# Now fix the route_task line: change back to original
# Find the line with "res = caller(prompt, effective_system)" and change it to not include task_type
for i, line in enumerate(lines):
    if "res = caller(prompt, effective_system)" in line:
        # Replace with original
        lines[i] = line.replace("res = caller(prompt, effective_system, task_type=tt)", "res = caller(prompt, effective_system)")
        break

# Write back
with open(file_path, 'w') as f:
    f.writelines(lines)

print("Original functions restored and route_task line fixed.")
