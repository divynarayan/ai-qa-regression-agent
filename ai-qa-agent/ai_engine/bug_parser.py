"""
Data structures for test plans and steps. Used by the test step generator and automation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class TestStep:
    """A single executable test step derived from a bug description."""
    step_number: int
    description: str
    action_type: str  # e.g. "open_app", "navigate", "verify"
    target: str | None = None
    expected: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestPlan:
    """Full test plan: bug summary + ordered steps."""
    test_name: str
    bug_description: str
    steps: List[TestStep]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "bug_description": self.bug_description,
            "steps": [s.to_dict() for s in self.steps],
        }
