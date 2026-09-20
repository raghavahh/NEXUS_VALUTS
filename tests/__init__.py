"""Test package initialization to ensure isolation before any project import."""

import os
import sys
import tempfile
from pathlib import Path

# Set test mode
os.environ["APP_MODE"] = "test"

# Create temporary directories for isolated test run
temp_dir = Path(tempfile.mkdtemp())
os.environ["NEXUS_DB_PATH"] = str(temp_dir / "nexus.db")
os.environ["NEXUS_STATE_DIR"] = str(temp_dir / "nexus_state")
os.environ["OUTPUT_DIR"] = str(temp_dir / "output")

# Set synthetic fake credentials (no real keys)
os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["NVIDIA_API_KEY"] = "test-nvidia-key"
os.environ["YOUTUBE_API_KEY"] = "test-youtube-key"

# Add the tests directory to sys.path so that _guard can be imported
tests_dir = Path(__file__).parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

# Now ensure isolation via the guard (will check that we are not in production)
import _guard
_guard.ensure_isolation()