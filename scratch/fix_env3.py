import sys

def fix_env(env_path):
    with open(env_path, 'rb') as f:
        data = f.read()
    # Split by newline (0x0A)
    chunks = data.split(b'\n')
    lines = []
    current = []
    for chunk in chunks:
        if chunk == b'':
            # Skip empty chunks from trailing newline
            continue
        current.append(chunk)
        combined = b''.join(current)
        if combined.count(b'=') == 1:
            lines.append(combined)
            current = []
    # If there is leftover, treat as a line (should not happen)
    if current:
        lines.append(b''.join(current))
    # Rejoin with newline and ensure final newline
    fixed_data = b'\n'.join(lines) + b'\n'
    with open(env_path, 'wb') as f:
        f.write(fixed_data)
    print(f'Fixed {env_path}')

if __name__ == '__main__':
    fix_env(r'c:/YT-SHORTS/.env')