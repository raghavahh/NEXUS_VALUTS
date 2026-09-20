import sys
file_path = 'c:/YT-SHORTS/core/llm_router.py'
with open(file_path, 'r') as f:
    lines = f.readlines()
# line 210 is index 209
if len(lines) > 209:
    del lines[209]
with open(file_path, 'w') as f:
    f.writelines(lines)
print('Removed line 210')
