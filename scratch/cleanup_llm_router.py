import sys

file_path = 'c:/YT-SHORTS/core/llm_router.py'
backup_path = 'c:/YT-SHORTS/core/llm_router.py.backup'

with open(file_path, 'r') as f:
    lines = f.readlines()

# We'll keep lines before the first gemini function (line 274 in 1-indexed)
# Convert to 0-index: line 274 -> index 273
# So we keep lines[0:273] (indices 0 to 272 inclusive)
keep_before = lines[0:273]

# Updated gemini function
updated_gemini = '''def call_gemini(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:
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
# Ensure newline at end
if not updated_gemini.endswith('\\n'):
    updated_gemini += '\\n'

# Keep lines after the second gemini function (we need to find where it ends)
# We'll find the line index of "import socket" after the second gemini function.
# Let's search for the line that starts with "import socket"
import_socket_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith("import socket"):
        import_socket_idx = i
        break

if import_socket_idx is None:
    print("Could not find import socket line")
    sys.exit(1)

# Keep lines from import_socket_idx to the end
keep_after = lines[import_socket_idx:]

# Combine
new_lines = keep_before + [updated_gemini] + keep_after

with open(file_path, 'w') as f:
    f.writelines(new_lines)

print("File rewritten")
