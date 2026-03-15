from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any


@dataclass
class TestStep:
    step_number: int
    description: str
    action_type: str  # e.g. "tap", "input_text", "assert_text"
    target: str | None = None
    value: str | None = None
    expected: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestPlan:
    id: str
    title: str
    bug_description: str
    expected_behavior: str
    steps: List[TestStep]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "bug_description": self.bug_description,
            "expected_behavior": self.expected_behavior,
            "steps": [s.to_dict() for s in self.steps],
        }


def _heuristic_steps_from_bug(bug_description: str, expected_behavior: str) -> List[TestStep]:
    """
    Lightweight, deterministic heuristic "AI" for converting a bug report
    into mobile test steps. This is intentionally simple so it can run
    without external model calls; you can replace it with a real LLM call.
    """
    bug = bug_description.strip()
    expected = expected_behavior.strip() or "Expected behavior as described in the bug report."

    if not bug:
        return []

    steps: List[TestStep] = []

    steps.append(
        TestStep(
            step_number=1,
            description="Launch the app on a clean install or logged-out state",
            action_type="launch_app",
            expected="App launches successfully without crashes.",
        )
    )

    lowered = bug.lower()
    if "login" in lowered or "sign in" in lowered:
        target_screen = "Login screen"
    elif "signup" in lowered or "register" in lowered:
        target_screen = "Signup screen"
    elif "settings" in lowered:
        target_screen = "Settings screen"
    elif "profile" in lowered:
        target_screen = "Profile screen"
    elif "checkout" in lowered or "payment" in lowered:
        target_screen = "Checkout screen"
    else:
        target_screen = "screen described in the bug"

    steps.append(
        TestStep(
            step_number=2,
            description=f"Navigate to the {target_screen}",
            action_type="navigate",
            expected=f"{target_screen} is visible.",
        )
    )

    steps.append(
        TestStep(
            step_number=3,
            description="Follow the user flow described in the bug report",
            action_type="execute_flow",
            value=bug,
            expected=expected,
        )
    )

    steps.append(
        TestStep(
            step_number=4,
            description="Verify UI, data, and logs align with expected behavior",
            action_type="assert_state",
            expected=expected,
        )
    )

    return steps


def generate_test_plan(
    bug_id: str,
    title: str,
    bug_description: str,
    expected_behavior: str,
) -> TestPlan:
    """
    Public API: convert a bug report into a structured TestPlan.

    To plug in a real LLM:
      - Replace `_heuristic_steps_from_bug` with a call to your model
      - Map model output back into `TestStep` objects.
    """
    steps = _heuristic_steps_from_bug(bug_description, expected_behavior)
    return TestPlan(
        id=bug_id,
        title=title or f"Bug {bug_id}",
        bug_description=bug_description,
        expected_behavior=expected_behavior,
        steps=steps,
    )

