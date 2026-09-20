import sys
file_path = 'c:/YT-SHORTS/core/llm_router.py'
with open(file_path, 'r') as f:
    lines = f.readlines()
# Remove line at index 145 (0-indexed) which is the broken line
if len(lines) > 145:
    del lines[145]
with open(file_path, 'w') as f:
    f.writelines(lines)
print('Removed line 145')
