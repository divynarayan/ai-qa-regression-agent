from __future__ import annotations

import re
from typing import Any, Dict, List


_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def substitute_vars(value: Any, data: Dict[str, Any]) -> Any:
    """
    Replaces `{{var}}` placeholders with values from test data.
    Works recursively across dict/list structures.
    """
    if value is None:
        return None
    if isinstance(value, str):
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in data:
                raise KeyError(f"Missing test data variable: {key}")
            return str(data[key])

        return _VAR.sub(repl, value)
    if isinstance(value, list):
        return [substitute_vars(v, data) for v in value]
    if isinstance(value, dict):
        return {k: substitute_vars(v, data) for k, v in value.items()}
    return value


def parse_steps(test_case: Dict[str, Any], test_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps = test_case.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("Test case `steps` must be a list.")
    parsed: List[Dict[str, Any]] = []
    for s in steps:
        if not isinstance(s, dict) or "action" not in s:
            raise ValueError(f"Each step must be an object with `action`. Got: {s!r}")
        parsed.append(substitute_vars(s, test_data))
    return parsed

