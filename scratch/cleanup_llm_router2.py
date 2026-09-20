import sys

file_path = 'c:/YT-SHORTS/core/llm_router.py'

with open(file_path, 'r') as f:
    lines = f.readlines()

# Keep lines before the first gemini function (line 274 in 1-indexed)
# 0-index: line 274 -> index 273
keep_before = lines[0:273]  # up to line 273 (line numbers 1-273)

# Updated gemini function as list of lines
gemini_lines = [
    'def call_gemini(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:\\n',
    '    """Google Gemini Cloud API caller using configuration from .env"""\\n',
    '    api_key = config.ai.gemini_api_key\\n',
    '    model = config.ai.gemini_model\\n',
    '    base_url = config.ai.gemini_api_url.rstrip("/")\\n',
    '    if not api_key:\\n',
    '        return None\\n',
    '    \\n',
    '    models_to_try = [model]\\n',
    '    for alt in ("gemini-3.5-flash", "gemini-3.8-flash", "gemini-3-flash-preview"):\\n',
    '        if alt not in models_to_try:\\n',
    '            models_to_try.append(alt)\\n',
    '    \\n',
    '    for current_model in models_to_try:\\n',
    '        url = f"{base_url}/models/{current_model}:generateContent?key={api_key}"\\n',
    '        # Set temperature and top_p based on task type\\n',
    '        if task_type in ("hooks", "script", "growth"):\\n',
    '            temperature = 1.0\\n',
    '            top_p = 0.95\\n',
    '        elif task_type in ("claim_verification", "storyboard_json", "seo_structure"):\\n',
    '            temperature = 0.2\\n',
    '            top_p = 0.95\\n',
    '        else:\\n',
    '            temperature = 0.7\\n',
    '            top_p = 0.9  # default for other task types\\n',
    '        payload = {\\n',
    '            "contents": [{"parts": [{"text": f"{system_prompt}\\\\n\\\\n{prompt}"}]}],\\n',
    '            "generationConfig": {"temperature": temperature, "top_p": top_p, "maxOutputTokens": 4096}\\n',
    '        }\\n',
    '        try:\\n',
    '            req = urllib.request.Request(\\n',
    '                url,\\n',
    '                data=json.dumps(payload).encode("utf-8"),\\n',
    '                headers={"Content-Type": "application/json"}\\n',
    '            )\\n',
    '            with urllib.request.urlopen(req, timeout=config.ai.request_timeout) as resp:\\n',
    '                data = json.loads(resp.read().decode("utf-8"))\\n',
    '                candidates = data.get("candidates", [])\\n',
    '                if candidates:\\n',
    '                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")\\n',
    '                    if text:\\n',
    '                        log.info(f"Generated via Gemini ({current_model})")\\n',
    '                        return text\\n',
    '        except urllib.error.HTTPError as e:\\n',
    '            log.warning(f"Gemini ({current_model}) HTTP {e.code}: {e.reason}")\\n',
    '            if e.code == 429:\\n',
    '                import time\\n',
    '                time.sleep(1.5)  # simple fixed wait for Gemini; could honor Retry-After but not required\\n',
    '        except Exception as e:\\n',
    '            log.warning(f"Gemini ({current_model}) error: {e}")\\n',
    '    return None\\n',
    '\\n'  # blank line after function
]

# Find the line index of "import socket" after the second gemini function
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
new_lines = keep_before + gemini_lines + keep_after

with open(file_path, 'w') as f:
    f.writelines(new_lines)

print("File rewritten")
