import sys
import re

def replace_between(file_path, start_marker, end_marker, new_text):
    with open(file_path, 'r') as f:
        content = f.read()
    # Find start and end positions
    start_idx = content.find(start_marker)
    if start_idx == -1:
        raise ValueError(f'Start marker not found: {start_marker}')
    # Find end marker after start
    end_idx = content.find(end_marker, start_idx + len(start_marker))
    if end_idx == -1:
        raise ValueError(f'End marker not found: {end_marker}')
    # We want to replace from start_idx to end_idx + len(end_marker)
    # Actually we want to replace the whole block including start and end markers? 
    # We'll replace from start_idx to end_idx + len(end_marker)
    # But we want to keep the end marker? We'll replace the block between start and end inclusive of start and end markers.
    # Simpler: replace the whole block from start_idx to end_idx + len(end_marker) with new_text.
    # However, new_text should include the start and end markers? We'll design new_text to be the replacement for the whole block.
    # We'll instead use a different approach: we'll split by lines and replace line ranges.
    # Let's do line-based.
    
def replace_lines(file_path, start_line, end_line, new_lines):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    # Convert to 0-index
    start_idx = start_line - 1
    end_idx = end_line - 1  # inclusive
    # Replace lines[start_idx:end_idx+1] with new_lines
    new_lines_with_nl = [line if line.endswith('\\n') else line + '\\n' for line in new_lines]
    # Ensure the last line ends with newline if not already
    # Actually we want to keep the newline separation.
    # We'll just insert the new lines and then join.
    lines[start_idx:end_idx+1] = new_lines_with_nl
    with open(file_path, 'w') as f:
        f.writelines(lines)

if __name__ == '__main__':
    file_path = 'c:/YT-SHORTS/core/llm_router.py'
    # We'll do each replacement separately.
    # First, call_openrouter lines 80-120
    with open(file_path, 'r') as f:
        lines = f.readlines()
    # lines are 0-indexed
    # line numbers: 80 -> index 79, 120 -> index 119 inclusive
    new_openrouter = '''def call_openrouter(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """OpenRouter Cloud API caller using configuration from .env"""
    api_key = config.ai.openrouter_api_key
    model = config.ai.openrouter_model
    base_url = config.ai.openrouter_api_url.rstrip("/")
    if not api_key:
        return None

    url = f"{base_url}/chat/completions"
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
        if e.code == 429:
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
            # bounded cool-down: max 1 retry/provider (handled by loop in route_task)
            time.sleep(wait_time)
    except Exception as e:
        log.warning(f"OpenRouter ({model}) error: {e}")
    return None
'''
    # Ensure newline at end
    if not new_openrouter.endswith('\\n'):
        new_openrouter += '\\n'
    # Replace lines 79 to 119 inclusive
    lines[79:120] = [new_openrouter]
    # Write back
    with open(file_path, 'w') as f:
        f.writelines(lines)
    print('Replaced call_openrouter')
    
    # Now read again for next replacement
    with open(file_path, 'r') as f:
        lines = f.readlines()
    # call_groq lines 122-164 -> indices 121 to 163 inclusive
    new_groq = '''def call_groq(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """Groq Cloud API caller using configuration from .env"""
    api_key = config.ai.groq_api_key
    model = config.ai.groq_model
    base_url = config.ai.groq_api_url.rstrip("/")
    if not api_key:
        return None

    url = f"{base_url}/chat/completions"
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
            # Honor Retry-After header if present
            retry_after = e.headers.get("Retry-After")
            if retry_after:
                try:
                    wait_time = int(retry_after)
                except ValueError:
                    wait_time = 5.0  # fallback
            else:
                wait_time = 5.0
            # bounded cool-down: max 1 retry/provider (handled by loop in route_task)
            time.sleep(wait_time)
    except Exception as e:
        log.warning(f"Groq ({model}) error: {e}")
    return None
'''
    if not new_groq.endswith('\\n'):
        new_groq += '\\n'
    lines[121:164] = [new_groq]
    with open(file_path, 'w') as f:
        f.writelines(lines)
    print('Replaced call_groq')
    
    # Now call_nvidia lines 166-203 -> indices 165 to 202 inclusive
    with open(file_path, 'r') as f:
        lines = f.readlines()
    new_nvidia = '''def call_nvidia(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    """NVIDIA NIM Cloud API caller using configuration from .env"""
    api_key = config.ai.nvidia_api_key
    model = config.ai.nvidia_model
    base_url = config.ai.nvidia_api_url.rstrip("/")
    if not api_key:
        return None

    url = f"{base_url}/chat/completions"
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
        if e.code == 429:
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
            # bounded cool-down: max 1 retry/provider (handled by loop in route_task)
            time.sleep(wait_time)
    except Exception as e:
        log.warning(f"NVIDIA NIM ({model}) error: {e}")
    return None
'''
    if not new_nvidia.endswith('\\n'):
        new_nvidia += '\\n'
    lines[165:203] = [new_nvidia]
    with open(file_path, 'w') as f:
        f.writelines(lines)
    print('Replaced call_nvidia')
    
    # Now call_gemini lines 205-245 -> indices 204 to 244 inclusive
    with open(file_path, 'r') as f:
        lines = f.readlines()
    new_gemini = '''def call_gemini(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
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
            if e.code == 429:
                import time
                time.sleep(1.5)  # simple fixed wait for Gemini; could honor Retry-After but not required
        except Exception as e:
            log.warning(f"Gemini ({current_model}) error: {e}")
    return None
'''
    if not new_gemini.endswith('\\n'):
        new_gemini += '\\n'
    lines[204:245] = [new_gemini]
    with open(file_path, 'w') as f:
        f.writelines(lines)
    print('Replaced call_gemini')
    
    # Now modify route_task line 299 (line number 299) to pass task_type
    with open(file_path, 'r') as f:
        lines = f.readlines()
    # line 299 is index 298 (0-indexed)
    # Original line:                 res = caller(prompt, effective_system)
    # We'll change to:                 res = caller(prompt, effective_system, task_type=tt)
    # But note: we need to have tt defined earlier; it is defined at line 277: tt = (task_type or \"general\").lower()
    # So we can use tt.
    # Let's get the line and replace.
    if 298 < len(lines):
        old_line = lines[298]
        # Replace the caller invocation
        # We'll do a simple string replace
        new_line = old_line.replace('res = caller(prompt, effective_system)', 'res = caller(prompt, effective_system, task_type=tt)')
        lines[298] = new_line
        with open(file_path, 'w') as f:
            f.writelines(lines)
        print('Modified route_task to pass task_type')
    else:
        print('Line 299 out of range')
