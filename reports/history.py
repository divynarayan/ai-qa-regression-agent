"""
Test run history: save JSON reports under reports/history/ and load last N for dashboard.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = PROJECT_ROOT / "reports" / "history"


def ensure_history_dir() -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR


def save_run_report(report: Dict[str, Any]) -> str:
    """Save a test run report as JSON. Returns path to the file."""
    ensure_history_dir()
    raw = report.get("timestamp", datetime.utcnow().isoformat() + "Z")
    ts = raw.replace(":", "-").replace(".", "-")[:19]
    platform = report.get("platform", "unknown")
    path = HISTORY_DIR / f"run_{platform}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return str(path)


def get_last_reports(n: int = 5) -> List[Dict[str, Any]]:
    """Load the last n test run reports (newest first)."""
    ensure_history_dir()
    files = sorted(HISTORY_DIR.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    reports = []
    for p in files[:n]:
        try:
            with open(p, encoding="utf-8") as f:
                reports.append(json.load(f))
        except Exception:
            continue
    return reports
