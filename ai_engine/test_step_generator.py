"""
Converts a bug description into test steps for the dashboard.
Supports both legacy display steps and structured executable steps for the executor.
"""

from __future__ import annotations

from typing import List, Dict, Any

from ai_engine.bug_parser import generate_test_plan
from ai_engine.structured_steps import generate_structured_steps


def generate_test_steps(bug_description: str) -> List[Dict[str, Any]]:
    """
    Convert a bug description into a list of test step dicts for display.
    Called by the dashboard when "Generate Test Steps" is clicked.
    """
    bug = (bug_description or "").strip()
    if not bug:
        return []

    plan = generate_test_plan(
        bug_id="regression",
        title="Regression test",
        bug_description=bug,
        expected_behavior="Expected behavior as described in the bug report.",
    )
    return [s.to_dict() for s in plan.steps]


def generate_executable_steps(bug_description: str) -> List[Dict[str, Any]]:
    """
    Generate structured steps executable by automation/executor.py.
    Format: [{"action": "open_app", "target": "settings"}, ...]
    """
    return generate_structured_steps(bug_description)
