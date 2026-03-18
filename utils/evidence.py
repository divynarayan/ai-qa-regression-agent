"""
Evidence collection: screenshots and screen recording.
Stores files under evidence/screenshots and evidence/recordings.
Used by the automation executor and integrated with test execution logging.
"""

import base64
import os
import time
from pathlib import Path
from typing import Optional

# Project root (parent of utils/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_SCREENSHOTS = PROJECT_ROOT / "evidence" / "screenshots"
EVIDENCE_RECORDINGS = PROJECT_ROOT / "evidence" / "recordings"


def _ensure_dirs() -> None:
    # Use both os.makedirs and Path.mkdir to be robust in different runtimes.
    os.makedirs(EVIDENCE_SCREENSHOTS, exist_ok=True)
    os.makedirs(EVIDENCE_RECORDINGS, exist_ok=True)
    EVIDENCE_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    EVIDENCE_RECORDINGS.mkdir(parents=True, exist_ok=True)


def capture_screenshot(
    driver,
    prefix: str = "step",
    subdir: Optional[str] = None,
) -> str:
    """
    Capture screenshot from Appium driver and save to evidence/screenshots.
    Returns absolute path of the saved file.
    """
    _ensure_dirs()
    out_dir = EVIDENCE_SCREENSHOTS / subdir if subdir else EVIDENCE_SCREENSHOTS
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    path = out_dir / f"{prefix}_{ts}.png"
    png = driver.get_screenshot_as_png()
    path.write_bytes(png)
    return str(path.resolve())


def start_recording(driver) -> None:
    """Start Appium screen recording. Call before test steps."""
    try:
        driver.start_recording_screen()
    except Exception:
        # Recording is optional; ignore capability issues.
        pass


def stop_recording(
    driver,
    prefix: str = "test",
    subdir: Optional[str] = None,
) -> Optional[str]:
    """
    Stop Appium screen recording and save to evidence/recordings.
    Returns path to saved .mp4 or None on failure.
    """
    _ensure_dirs()
    out_dir = EVIDENCE_RECORDINGS / subdir if subdir else EVIDENCE_RECORDINGS
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        payload = driver.stop_recording_screen()
        ts = int(time.time() * 1000)
        path = out_dir / f"{prefix}_{ts}.mp4"
        path.write_bytes(base64.b64decode(payload))
        return str(path.resolve())
    except Exception:
        return None
