with open('C:/YT-SHORTS/main.py', 'r') as f:
    content = f.read()

# Find run_pipeline function
import re
pattern = r'def run_pipeline\([^)]*\):'
matches = list(re.finditer(pattern, content))

print("Found run_pipeline at positions:")
for match in matches:
    print(f"  Position {match.start()}: {match.group()}")

# Extract the function
if matches:
    start = matches[0].start()
    # Find the end of the function (next function definition or end of file)
    next_def = content.find('\ndef ', start + 1)
    if next_def == -1:
        next_def = len(content)
    
    function_text = content[start:next_def]
    print("\nrun_pipeline function:")
    print(function_text)
else:
    print("run_pipeline function not found")