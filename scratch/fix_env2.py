import sys

def fix_env(env_path):
    with open(env_path, 'rb') as f:
        data = f.read()
    # Replace newline characters that are not at the end of a line? 
    # Instead, split by newline and reconstruct.
    text = data.decode('utf-8')
    lines = text.split('\\n')
    # Now we need to merge lines that are continuations.
    # We'll assume that a line that does not contain '=' is a continuation of the previous line.
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if '=' in line:
            fixed_lines.append(line)
            i += 1
        else:
            # This line is a continuation of the previous line
            if fixed_lines:
                fixed_lines[-1] += line
            else:
                # Should not happen, but just in case
                fixed_lines.append(line)
            i += 1
    # Join with newline
    fixed_text = '\\n'.join(fixed_lines)
    # Write back
    with open(env_path, 'wb') as f:
        f.write(fixed_text.encode('utf-8'))
    print(f'Fixed {env_path}')

if __name__ == '__main__':
    fix_env(r'c:/YT-SHORTS/.env')