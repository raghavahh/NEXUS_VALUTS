import sys
import logging
sys.path.insert(0, "C:/YT-SHORTS")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
from core.llm_router import route_task
response = route_task("Hello, world!", task_type="general")
print("Response:", response[:100] if response else "None")
