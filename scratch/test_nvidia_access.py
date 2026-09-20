import sys
sys.path.insert(0, "C:/YT-SHORTS")
import os
import urllib.request
import json
from core.config import config

api_key = config.ai.nvidia_api_key
if not api_key:
    print("NVIDIA API key not set")
    sys.exit(1)

base_url = config.ai.nvidia_api_url.rstrip("/")
model_id = config.ai.nvidia_model

print(f"Testing NVIDIA API access for model: {model_id}")
print(f"Base URL: {base_url}")

# Step 1: Check /v1/models
models_url = f"{base_url}/models"
print(f"\n1. Calling {models_url}")
req = urllib.request.Request(models_url, headers={"Authorization": f"Bearer {api_key}"})
try:
    with urllib.request.urlopen(req) as resp:
        models_data = json.load(resp)
        model_ids = [m.get("id") for m in models_data.get("data", [])]
        print(f"   HTTP Status: {resp.status}")
        if model_id in model_ids:
            print(f"   Model '{model_id}' found in the list.")
        else:
            print(f"   Model '{model_id}' NOT found in the list.")
            print(f"   Available models (first 5): {model_ids[:5]}")
except Exception as e:
    print(f"   ERROR: {e}")
    # Try to read error body if available
    if hasattr(e, 'read'):
        try:
            error_body = e.read().decode('utf-8')
            print(f"   Error body: {error_body}")
        except:
            pass
    sys.exit(1)

# Step 2: Tiny chat call
chat_url = f"{base_url}/chat/completions"
print(f"\n2. Making a tiny chat call to {chat_url}")
payload = {
    "model": model_id,
    "messages": [
        {"role": "user", "content": "Say 'hello' in one word."}
    ],
    "max_tokens": 10,
    "temperature": 0.0
}
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    chat_url,
    data=data,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp_data = json.load(resp)
        print(f"   HTTP Status: {resp.status}")
        text = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"   Response: {text.strip()}")
except urllib.error.HTTPError as e:
    print(f"   HTTP Error: {e.code} {e.reason}")
    try:
        error_body = e.read().decode('utf-8')
        print(f"   Error body: {error_body}")
    except:
        pass
except Exception as e:
    print(f"   ERROR: {e}")
