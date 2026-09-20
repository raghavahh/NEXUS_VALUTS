import sys
file_path = 'c:/YT-SHORTS/core/llm_router.py'
with open(file_path, 'r') as f:
    lines = f.readlines()
# line numbers are 1-indexed
# line 145 is index 144
if len(lines) > 144:
    lines[144] = 'def call_groq(prompt: str, system_prompt: str = "", task_type: str = "general") -> Optional[str]:\n'
with open(file_path, 'w') as f:
    f.writelines(lines)
print('Fixed line 145')
