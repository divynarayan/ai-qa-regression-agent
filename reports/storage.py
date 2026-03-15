from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


REPORTS_DIR = Path("reports") / "runs"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_report(plan_id: str, platform: str, data: Dict[str, Any]) -> str:
    """
    Persist a regression test report as JSON and return the file path.
    """
    ts = int(time.time() * 1000)
    filename = f"{plan_id}_{platform}_{ts}.json"
    path = REPORTS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(path)

