import sys

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

file_path = 'c:/YT-SHORTS/core/llm_router.py'

# New function bodies with temperature split and circuit breaker (retry once on 429)
new_openrouter = '''def call_openrouter(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """OpenRouter Cloud API caller using configuration from .env"""
    api_key = config.ai.openrouter_api_key
    model = config.ai.openrouter_model
    base_url = config.ai.openrouter_api_url.rstrip("/")
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
        top_p = 0.9  # default for other task types

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

    max_attempts = 2
    for attempt in range(max_attempts):
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
            if e.code == 429 and attempt < max_attempts - 1:
                import time
                # Honor Retry-After header if present
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 5.0  # fallback
                else:
                    wait_time = 5.0
                # bounded cool-down: we will retry once (handled by loop)
                time.sleep(wait_time)
            else:
                # If not 429 or last attempt, we will fail after loop
                pass
        except Exception as e:
            log.warning(f"OpenRouter ({model}) error: {e}")
            break
    return None
'''

new_groq = '''def call_groq(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
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
        top_p = 0.9  # default for other task_types

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "Documentary intelligence system."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": 6000
    }

    max_attempts = 2
    for attempt in range(max_attempts):
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
            if e.code == 429 and attempt < max_attempts - 1:
                import time
                # Honor Retry-After header if present
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 5.0  # fallback
                else:
                    wait_time = 5.0
                time.sleep(wait_time)
            else:
                pass
        except Exception as e:
            log.warning(f"Groq ({model}) error: {e}")
            break
    return None
'''

new_nvidia = '''def call_nvidia(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
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
        top_p = 0.9  # default for other task types (keeping original temperature 0.6 for general?)

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
            if e.code == 429 and attempt < max_attempts - 1:
                import time
                # Honor Retry-After header if present
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 5.0  # fallback
                else:
                    wait_time = 5.0
                time.sleep(wait_time)
            else:
                pass
        except Exception as e:
            log.warning(f"NVIDIA NIM ({model}) error: {e}")
            break
    return None
'''

new_gemini = '''def call_gemini(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """Google Gemini Cloud API caller using configuration from .env"""
    api_key = config.ai.gemini_api_key
    model = config.ai.gemini_model
    base_url = config.ai.gemini_api_url.rstrip("/")
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
        top_p = 0.9  # default for other task_types

    models_to_try = [model]
    for alt in ("gemini-3.5-flash", "gemini-3.8-flash", "gemini-3-flash-preview"):
        if alt not in models_to_try:
            models_to_try.append(alt)

    max_attempts = 2
    for attempt in range(max_attempts):
        for current_model in models_to_try:
            url = f"{base_url}/models/{current_model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{system_prompt}\\n\\n{prompt}"}]}],
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
                if e.code == 429 and attempt < max_attempts - 1:
                    import time
                    time.sleep(1.5)  # simple fixed wait for Gemini; could honor Retry-After but not required
                # If not 429 or last attempt, we will break after the inner loop? We'll break to outer loop to retry with next model? Actually we want to retry the same model once.
                # We'll break the inner loop and let the outer loop handle retry? We'll just continue to next attempt (which will retry the same model list again).
                # We'll set a flag to break the inner loop and go to next attempt.
                break  # break inner loop to go to next attempt
            except Exception as e:
                log.warning(f"Gemini ({current_model}) error: {e}")
                break
        else:
            # If inner loop didn't break, we succeeded and returned already
            continue
        # If inner loop broke due to 429 and we have another attempt, we will retry the same model list
        # If we are out of attempts, we will fall through to return None
        if attempt < max_attempts - 1:
            continue
        else:
            break
    return None
'''

# Read the file
with open(file_path, 'r') as f:
    lines = f.readlines()

# Replace each function with the new version
lines = replace_function(lines, "call_openrouter", new_openrouter)
lines = replace_function(lines, "call_groq", new_groq)
lines = replace_function(lines, "call_nvidia", new_nvidia)
lines = replace_function(lines, "call_gemini", new_gemini)

# Now modify route_task to pass task_type to the caller
# Find the line with "res = caller(prompt, effective_system)" and change it to include task_type
for i, line in enumerate(lines):
    if "res = caller(prompt, effective_system)" in line:
        lines[i] = line.replace("res = caller(prompt, effective_system)", "res = caller(prompt, effective_system, task_type=tt)")
        break

# Write back
with open(file_path, 'w') as f:
    f.writelines(lines)

print("Applied temperature split and circuit breaker changes, and updated route_task to pass task_type.")
