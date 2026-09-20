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
url = f"{base_url}/models"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
        model_ids = [model.get("id") for model in data.get("data", [])]
        target_model = config.ai.nvidia_model
        if target_model in model_ids:
            print(f"Model ID '{target_model}' found in NVIDIA /v1/models list")
        else:
            print(f"Model ID '{target_model}' NOT found in NVIDIA /v1/models list")
            print("Available models (first 5):", model_ids[:5])
except Exception as e:
    print("Error calling NVIDIA /v1/models:", e)
