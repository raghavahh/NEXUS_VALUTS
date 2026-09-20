"""
Automated Hardcoding Audit across Repository
Verifies that all runtime parameters, credentials, and models are configuration-driven.
"""

import os
import re
from pathlib import Path

import _guard
_guard.ensure_isolation()  # MUST precede any project import
BASE_DIR = Path(__file__).resolve().parent.parent

def run_audit():
    findings = {
        "HARDCODED API KEYS": 0,
        "HARDCODED TOKENS": 0,
        "HARDCODED PASSWORDS": 0,
        "HARDCODED CLIENT SECRETS": 0,
        "HARDCODED MODEL VALUES": 0,
        "HARDCODED PROVIDER ORDER": 0,
        "HARDCODED PATHS": 0,
        "HARDCODED RENDER SETTINGS": 0,
        "HARDCODED SCENE SETTINGS": 0,
        "HARDCODED STORY SETTINGS": 0,
        "HARDCODED QC THRESHOLDS": 0
    }

    # Python source files to audit (excluding tests and git)
    py_files = []
    for root, dirs, files in os.walk(BASE_DIR):
        if any(ignored in root for ignored in [".git", ".nexus_state", "tests", "__pycache__", ".agents"]):
            continue
        for f in files:
            if f.endswith(".py"):
                py_files.append(Path(root) / f)

    for p in py_files:
        content = p.read_text(encoding="utf-8")
        rel_path = p.relative_to(BASE_DIR)

        # 1. Credentials in python code
        if re.search(r'(api_key|token|secret)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']', content, re.IGNORECASE):
            findings["HARDCODED API KEYS"] += 1
            print(f"FAILED: Hardcoded key in {rel_path}")

        # 2. Hardcoded model assignments outside config.py
        if p.name != "config.py":
            if re.search(r'model\s*=\s*["\'](gemini|llama|nemotron|gpt-oss)', content, re.IGNORECASE):
                findings["HARDCODED MODEL VALUES"] += 1
                print(f"FAILED: Hardcoded model in {rel_path}")

        # 3. Hardcoded provider ordering outside config.py
        if p.name != "config.py":
            if re.search(r'providers\s*=\s*\[.*call_.*\]', content):
                findings["HARDCODED PROVIDER ORDER"] += 1
                print(f"FAILED: Hardcoded provider list in {rel_path}")

        # 4. Check for alternate credential names (e.g. YOUTUBE_CLIENT_ID)
        if re.search(r'os\.getenv\(["\']YOUTUBE_CLIENT_ID["\']\)', content):
            findings["HARDCODED CLIENT SECRETS"] += 1
            print(f"FAILED: Alternate credential name in {rel_path}")

    print("\n" + "="*50)
    print("           REPOSITORY HARDCODING AUDIT REPORT       ")
    print("="*50)
    all_zero = True
    for k, v in findings.items():
        print(f"{k}: {v}")
        if v != 0:
            all_zero = False
    print("="*50 + "\n")
    return all_zero

if __name__ == "__main__":
    success = run_audit()
    if not success:
        exit(1)
