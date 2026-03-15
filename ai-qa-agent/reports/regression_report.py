"""
Generate and save JSON regression reports. Reports are stored under reports/.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict

import sys
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import REPORTS_DIR, ensure_dirs


def save_regression_report(result: Dict[str, Any]) -> str:
    """
    Save a test result as a JSON report. Result must include at least:
    test_name, platform, status; optionally screenshot, video, error.
    Returns the path of the saved file.
    """
    ensure_dirs()
    ts = int(time.time() * 1000)
    name = f"{result.get('test_name', 'test')}_{result.get('platform', 'unknown')}_{ts}.json"
    path = REPORTS_DIR / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return str(path.resolve())
