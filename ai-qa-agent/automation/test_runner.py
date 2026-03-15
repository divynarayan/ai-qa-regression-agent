"""
Test runner: invokes iOS or Android regression test and returns result dict for the dashboard.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from automation.ios_test import run_ios_test
from automation.android_test import run_android_test


def run_ios_regression_test(test_name: str = "ios_wifi_test") -> dict:
    """Run iOS Settings → Wi-Fi test. Returns result with status, screenshot path, video path."""
    return run_ios_test(test_name=test_name)


def run_android_regression_test(test_name: str = "android_wifi_test") -> dict:
    """Run Android Settings → Wi-Fi test. Returns result with status, screenshot path, video path."""
    return run_android_test(test_name=test_name)
