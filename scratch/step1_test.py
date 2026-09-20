import sys
import os
sys.path.insert(0, 'c:/YT-SHORTS')

# Override model via environment before importing config
os.environ['NVIDIA_MODEL'] = 'nvidia/nemotron-3-super-120b-a12b'
# Ensure API URL is correct (default is fine)
os.environ['NVIDIA_API_URL'] = 'https://integrate.api.nvidia.com/v1'

from core.config import config
import urllib.request
import urllib.error
import json

# Helper to make HTTP requests and print status/error without key
def http_request(url, data=None, headers=None, method='GET', timeout=10):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8'), dict(resp.getheaders())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8'), dict(e.headers)
    except Exception as e:
        return None, str(e), {}

# 1. Test NVIDIA /v1/models
print('=== Testing NVIDIA /v1/models ===')
models_url = f'{config.ai.nvidia_api_url}/models'
api_key = config.ai.nvidia_api_key
if not api_key:
    print('ERROR: NVIDIA API key not configured')
    sys.exit(1)
headers = {
    'Authorization': f'Bearer {api_key}',
    'Accept': 'application/json',
    'HTTP-Referer': 'https://github.com/nexus-vaults',
    'X-Title': 'Nexus Vaults Engine'
}
status, body, resp_headers = http_request(models_url, headers=headers, timeout=config.ai.request_timeout)
print(f'HTTP Status: {status}')
if status != 200:
    print(f'Error Response: {body[:200]}')
else:
    print(f'Response (first 200 chars): {body[:200]}')

# 2. Test a tiny chat call to nvidia/nemotron-3-super-120b-a12b
print('\n=== Testing NVIDIA chat completion ===')
chat_url = f'{config.ai.nvidia_api_url}/chat/completions'
payload = {
    'model': config.ai.nvidia_model,
    'messages': [{'role': 'user', 'content': 'Say \"hello\" in one word.'}],
    'max_tokens': 5,
    'temperature': 0.0
}
data = json.dumps(payload).encode('utf-8')
chat_headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json',
    'HTTP-Referer': 'https://github.com/nexus-vaults',
    'X-Title': 'Nexus Vaults Engine'
}
status, body, resp_headers = http_request(chat_url, data=data, headers=chat_headers, method='POST', timeout=config.ai.request_timeout)
print(f'HTTP Status: {status}')
if status != 200:
    print(f'Error Response: {body[:200]}')
else:
    print(f'Response (first 200 chars): {body[:200]}')

# 3. Now test route_task and see which provider answers
print('\n=== Testing route_task ===')
from core.llm_router import PROVIDER_DISPATCH, route_task

call_log = []
original_dispatch = PROVIDER_DISPATCH.copy()

def make_wrapper(name, func):
    def wrapper(*args, **kwargs):
        call_log.append(name)
        return func(*args, **kwargs)
    return wrapper

for name, func in original_dispatch.items():
    PROVIDER_DISPATCH[name] = make_wrapper(name, func)

try:
    answer = route_task('Say \"hello\" in one word.', task_type='general')
    print(f'route_task returned: {answer}')
    print(f'Providers called (in order): {call_log}')
except Exception as e:
    print(f'route_task raised: {e}')
finally:
    PROVIDER_DISPATCH.clear()
    PROVIDER_DISPATCH.update(original_dispatch)

# 4. Print the actual provider order per role
print('\n=== Provider order per role (as computed by route_task) ===')
from core.llm_router import config as cfg

def get_ordered_chain(task_type):
    tt = (task_type or 'general').lower()
    if tt in ('critic', 'scoring', 'quality_pass', 'critique', 'hook'):
        role_pref = ['gemini', 'groq', 'nvidia', 'openrouter']
    elif tt in ('generation', 'story', 'script', 'research', 'visual_intent', 'storyboard'):
        role_pref = ['gemini', 'groq', 'nvidia', 'openrouter']
    elif tt in ('fast', 'formatting', 'seo'):
        role_pref = ['groq', 'gemini', 'nvidia', 'openrouter']
    else:
        role_pref = [p.lower().strip() for p in cfg.ai.provider_chain]
    configured_chain = [p.lower().strip() for p in cfg.ai.provider_chain]
    ordered_chain = [p for p in role_pref if p in configured_chain]
    for p in configured_chain:
        if p not in ordered_chain:
            ordered_chain.append(p)
    return ordered_chain

for role_name, task_types in [
    ('critic', ['critic', 'scoring', 'quality_pass', 'critique', 'hook']),
    ('generation', ['generation', 'story', 'script', 'research', 'visual_intent', 'storyboard']),
    ('fast', ['fast', 'formatting', 'seo']),
    ('general', ['general'])
]:
    tt = task_types[0]
    order = get_ordered_chain(tt)
    print(f'{role_name:10} (tt={tt:8}) -> {order}')

print(f'\nConfigured AI_PROVIDER_CHAIN: {config.ai.provider_chain}')