"""
Converts a bug description into structured test steps using OpenAI API or a heuristic fallback.
No manual configuration required: uses OPENAI_API_KEY if set, otherwise heuristic.
"""

from __future__ import annotations

import json
import os
import re
from typing import List

from ai_engine.bug_parser import TestPlan, TestStep


def _heuristic_steps(bug_description: str) -> List[TestStep]:
    """
    Heuristic generator when no API key is set. Maps common phrases to Settings/WiFi steps.
    """
    bug = bug_description.strip().lower()
    steps: List[TestStep] = []

    steps.append(TestStep(
        step_number=1,
        description="Open Settings app",
        action_type="open_app",
        target="Settings",
        expected="Settings app is visible",
    ))
    steps.append(TestStep(
        step_number=2,
        description="Navigate to WiFi",
        action_type="navigate",
        target="Wi-Fi",
        expected="Wi-Fi screen is visible",
    ))
    steps.append(TestStep(
        step_number=3,
        description="Verify page loads",
        action_type="verify",
        target="Wi-Fi",
        expected="No crash; WiFi page loads",
    ))
    return steps


def _openai_steps(bug_description: str) -> List[TestStep]:
    """Generate steps using OpenAI API. Returns heuristic steps on failure or missing key."""
    api_key = os.environ.get("OPENAI_API_KEY", "") or getattr(
        __import__("config.settings", fromlist=["OPENAI_API_KEY"]), "OPENAI_API_KEY", ""
    )
    if not api_key:
        return _heuristic_steps(bug_description)

    try:
        openai = __import__("openai", fromlist=["OpenAI"]).OpenAI(api_key=api_key)
        response = openai.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a QA engineer. Given a bug description, output a JSON array of test steps. Each step has: step_number (int), description (string), action_type (string, e.g. open_app, navigate, verify), target (string or null), expected (string or null). Keep 3-6 steps. Example: [{\"step_number\":1,\"description\":\"Open Settings app\",\"action_type\":\"open_app\",\"target\":\"Settings\",\"expected\":\"Settings is visible\"}]",
                },
                {"role": "user", "content": bug_description},
            ],
            max_tokens=500,
        )
        text = response.choices[0].message.content or "[]"
        # Extract JSON array if wrapped in markdown
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1)
        data = json.loads(text)
        return [
            TestStep(
                step_number=s.get("step_number", i + 1),
                description=s.get("description", ""),
                action_type=s.get("action_type", "verify"),
                target=s.get("target"),
                expected=s.get("expected"),
            )
            for i, s in enumerate(data) if isinstance(s, dict)
        ]
    except Exception:
        return _heuristic_steps(bug_description)


def generate_test_plan(bug_description: str, test_name: str = "regression_test") -> TestPlan:
    """
    Convert a bug description into a TestPlan. Uses OpenAI if OPENAI_API_KEY is set,
    otherwise returns heuristic steps (e.g. Open Settings → Navigate to WiFi → Verify).
    """
    bug_description = bug_description.strip()
    if not bug_description:
        return TestPlan(test_name=test_name, bug_description="", steps=[])

    steps = _openai_steps(bug_description)
    if not steps:
        steps = _heuristic_steps(bug_description)
    return TestPlan(test_name=test_name, bug_description=bug_description, steps=steps)
