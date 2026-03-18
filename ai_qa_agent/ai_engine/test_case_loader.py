from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml


def load_yaml_test_case(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("YAML test case must parse to a mapping/object.")
    if "id" not in data or "steps" not in data:
        raise ValueError("YAML test case must include `id` and `steps`.")
    if not isinstance(data["steps"], list):
        raise ValueError("YAML `steps` must be a list.")
    return data


def load_json_test_data(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON test data must parse to an object.")
    return data


def load_from_paths(test_case_path: str | Path, test_data_path: str | Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return load_yaml_test_case(test_case_path), load_json_test_data(test_data_path)


def load_from_content(test_case_yaml: str, test_data_json: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    tc = yaml.safe_load(test_case_yaml)
    td = json.loads(test_data_json)
    if not isinstance(tc, dict):
        raise ValueError("Uploaded YAML test case must parse to an object.")
    if not isinstance(td, dict):
        raise ValueError("Uploaded JSON test data must parse to an object.")
    if "id" not in tc or "steps" not in tc or not isinstance(tc["steps"], list):
        raise ValueError("Uploaded YAML test case must include `id` and list `steps`.")
    return tc, td

