"""
Converts a bug description into structured test steps for the dashboard.
Uses ai_engine.bug_parser.generate_test_plan so no duplicate logic.
"""

from __future__ import annotations

from typing import List, Dict, Any

from ai_engine.bug_parser import generate_test_plan


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
