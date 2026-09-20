import sys

def main():
    env_path = r'c:/YT-SHORTS/.env'
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Fix line 71 (index 70) - NVIDIA_MODEL
    lines[70] = 'NVIDIA_MODEL=nvidia/nemotron-3-super-120b-a12b\\n'
    # Fix line 72 (index 71) - NVIDIA_API_URL
    lines[71] = 'NVIDIA_API_URL=https://integrate.api.nvidia.com/v1\\n'
    # Fix line 74 (index 73) - GROQ_MODEL
    lines[73] = 'GROQ_MODEL=openai/gpt-oss-120b\\n'
    
    with open(env_path, 'w') as f:
        f.writelines(lines)
    print('Fixed .env file')

if __name__ == '__main__':
    main()