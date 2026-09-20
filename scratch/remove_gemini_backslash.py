import sys
file_path = 'c:/YT-SHORTS/core/llm_router.py'
with open(file_path, 'r') as f:
    lines = f.readlines()
# line 274 is index 273
if len(lines) > 273:
    del lines[273]
with open(file_path, 'w') as f:
    f.writelines(lines)
print('Removed line 274')
