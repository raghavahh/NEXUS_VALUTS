import sys
file_path = 'c:/YT-SHORTS/core/llm_router.py'
with open(file_path, 'r') as f:
    lines = f.readlines()
# We'll replace lines 210 to 248 inclusive (0-indexed indices 209 to 247)
# But we need to be sure of the exact range.
# Let's instead find the line with the docstring and the line before def call_gemini.
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith('\"\"\"NVIDIA NIM Cloud API caller'):
        start_idx = i
    if line.strip().startswith('def call_gemini') and start_idx is not None:
        end_idx = i
        break
if start_idx is not None and end_idx is not None:
    # Replace lines[start_idx:end_idx] with new nvidia function
    new_nvidia = '''def call_nvidia(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    \"\"\"NVIDIA NIM Cloud API caller using configuration from .env\"\"\"
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
    new_lines = new_nvidia.splitlines(keepends=True)
    lines[start_idx:end_idx] = new_lines
    with open(file_path, 'w') as f:
        f.writelines(lines)
    print('Replaced call_nvidia')
else:
    print('Could not locate boundaries for nvidia replacement')
