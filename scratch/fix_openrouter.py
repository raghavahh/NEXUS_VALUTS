import sys

file_path = 'c:/YT-SHORTS/core/llm_router.py'

with open(file_path, 'r') as f:
    lines = f.readlines()

# Define the new call_openrouter function
new_openrouter = '''def call_openrouter(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
    \"\"\"OpenRouter Cloud API caller using configuration from .env\"\"\"
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

# Find the start and end indices of the function
# We'll replace from line 80 to the line before "def call_groq"
# Find the line index of "def call_groq"
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith("def call_openrouter"):
        start_idx = i
    if line.strip().startswith("def call_groq") and start_idx is not None:
        end_idx = i
        break

if start_idx is not None and end_idx is not None:
    # Replace lines[start_idx:end_idx] with new_openrouter lines
    # Split new_openrouter into lines
    new_lines = new_openrouter.splitlines(keepends=True)
    lines[start_idx:end_idx] = new_lines
    with open(file_path, 'w') as f:
        f.writelines(lines)
    print("Replaced call_openrouter")
else:
    print("Could not locate function boundaries")
