"""
AI Video Factory - State Persistence Store
Prevents git repo pollution by storing channel.db as GitHub Actions Artifacts
or external storage rather than committing binary DBs to git history.
"""

import os
import shutil
from pathlib import Path
from core.config import DB_PATH, config
from core.logging import log

# Test isolation: when AI_VIDEO_FACTORY_TEST_SANDBOX is set (by tests/_guard.py), state
# persistence is redirected into the sandbox — never the production .factory_state.
def _state_backup_dir() -> Path:
    sandbox = os.getenv("AI_VIDEO_FACTORY_TEST_SANDBOX")
    return Path(sandbox) / ".factory_state" if sandbox else config.storage.state_dir

STATE_BACKUP_DIR = _state_backup_dir()

def load_state() -> bool:
    """
    Restores the database state at the beginning of a cloud or local run.
    In GitHub Actions, workflow downloads artifact 'factory-db-state' into .factory_state/
    """
    STATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    incoming_db = STATE_BACKUP_DIR / "channel.db"
    
    if incoming_db.exists():
        if DB_PATH.exists():
            if incoming_db.stat().st_mtime > DB_PATH.stat().st_mtime:
                log.info(f"Restoring newer persistent state from {incoming_db} -> {DB_PATH}")
                shutil.copy2(incoming_db, DB_PATH)
            else:
                log.info(f"Using existing local state database: {DB_PATH} (newer or equal to backup)")
        else:
            log.info(f"Restoring persistent state from {incoming_db} -> {DB_PATH}")
            shutil.copy2(incoming_db, DB_PATH)
        return True
    elif DB_PATH.exists():
        log.info(f"Using existing local state database: {DB_PATH}")
        return True
    else:
        log.info("No prior state found. Starting with a fresh database initialization.")
        return False

def save_state() -> Path:
    """
    Prepares the state database for export/upload as an artifact at the end of the run.
    """
    STATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target_path = STATE_BACKUP_DIR / "channel.db"
    if DB_PATH.exists():
        # Local runs commonly use .factory_state/channel.db as both the live
        # database and the export location. shutil.copy2 rejects that case.
        if DB_PATH.resolve() != target_path.resolve():
            shutil.copy2(DB_PATH, target_path)
        log.info(f"State successfully packaged for persistence at {target_path}")
        return target_path
    else:
        log.warning(f"No DB found at {DB_PATH} to save.")
        return target_path
