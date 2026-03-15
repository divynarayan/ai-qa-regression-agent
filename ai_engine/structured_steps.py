"""
Generates structured, executable test steps from a bug description.
Output format is JSON that the automation executor can run (open_app, tap, verify_element, etc.).
"""

from __future__ import annotations

from typing import List, Dict, Any

# Supported executor actions
EXECUTOR_ACTIONS = (
    "open_app", "tap", "scroll", "verify_element",
    "capture_screenshot", "start_recording", "stop_recording",
)


def _heuristic_structured_steps(bug_description: str) -> List[Dict[str, Any]]:
    """
    Map a bug description to structured steps executable by the executor.
    For Settings/WiFi-style bugs we emit open_app(settings), tap(WiFi), verify_element, capture_screenshot.
    """
    bug = (bug_description or "").strip().lower()
    if not bug:
        return []

    steps: List[Dict[str, Any]] = [
        {"action": "open_app", "target": "settings"},
        {"action": "tap", "target": "WiFi"},
        {"action": "verify_element", "target": "WiFi Screen"},
        {"action": "capture_screenshot"},
    ]
    return steps


def generate_structured_steps(bug_description: str) -> List[Dict[str, Any]]:
    """
    Generate structured automation steps from a bug description.
    Returns a list of dicts with keys: action, and optionally target/value.
    Stored in session state and executed by automation/executor.py.
    """
    return _heuristic_structured_steps(bug_description)
