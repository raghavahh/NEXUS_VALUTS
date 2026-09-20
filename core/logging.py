"""
NEXUS VAULTS 2.0 - Structured Console & Audit Logging
"""

import sys
import logging
from datetime import datetime

# Windows GitHub Actions runner console uses cp1252 by default; ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class NexusFormatter(logging.Formatter):
    GREY = "\x1b[38;20m"
    CYAN = "\x1b[36;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: GREY + "[%(asctime)s] [DEBUG] %(message)s" + RESET,
        logging.INFO: CYAN + "[%(asctime)s] 📁 %(message)s" + RESET,
        logging.WARNING: YELLOW + "[%(asctime)s] ⚠️  %(message)s" + RESET,
        logging.ERROR: RED + "[%(asctime)s] ❌ %(message)s" + RESET,
        logging.CRITICAL: BOLD_RED + "[%(asctime)s] 🚨 %(message)s" + RESET,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

def setup_logger(name: str = "nexus") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(NexusFormatter())
        logger.addHandler(handler)
    return logger

log = setup_logger()
