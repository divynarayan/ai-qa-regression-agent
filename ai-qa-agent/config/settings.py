"""
Central configuration for the AI QA Regression Testing Agent.
All paths and settings are resolved from the project root; no manual editing required.
"""

import os
from pathlib import Path

# Project root: directory containing config/ (i.e. ai-qa-agent)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Appium
APPIUM_URL = os.environ.get("APPIUM_URL", "http://127.0.0.1:4723")

# iOS Simulator (override via env if needed)
IOS_DEVICE_NAME = os.environ.get("IOS_DEVICE_NAME", "iPhone 16")
IOS_PLATFORM_VERSION = os.environ.get("IOS_PLATFORM_VERSION", "18.0")
IOS_BUNDLE_ID_SETTINGS = "com.apple.Preferences"

# Android Emulator
ANDROID_DEVICE_NAME = os.environ.get("ANDROID_DEVICE_NAME", "Android Emulator")
ANDROID_PLATFORM_VERSION = os.environ.get("ANDROID_PLATFORM_VERSION", "14.0")
ANDROID_SETTINGS_PACKAGE = "com.android.settings"
ANDROID_SETTINGS_ACTIVITY = "com.android.settings.Settings"

# Evidence storage (screenshots, recordings, logs)
EVIDENCE_ROOT = PROJECT_ROOT / "evidence"
SCREENSHOTS_DIR = EVIDENCE_ROOT / "screenshots"
RECORDINGS_DIR = EVIDENCE_ROOT / "recordings"
LOGS_DIR = EVIDENCE_ROOT / "logs"

# Reports (JSON regression reports)
REPORTS_DIR = PROJECT_ROOT / "reports"

# OpenAI (optional; if not set, heuristic test-step generator is used)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def ensure_dirs() -> None:
    """Create evidence and report directories if they do not exist."""
    for d in (SCREENSHOTS_DIR, RECORDINGS_DIR, LOGS_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
