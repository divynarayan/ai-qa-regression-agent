"""
Screen recording utilities using Appium's start_recording_screen / stop_recording_screen.
Saves videos under evidence/recordings/.
"""

import base64
import time
from pathlib import Path
from typing import Optional

from config.settings import RECORDINGS_DIR, ensure_dirs


def start_recording(driver) -> None:
    """Start Appium screen recording. Call before test steps."""
    try:
        driver.start_recording_screen()
    except Exception:
        pass


def stop_recording(driver, prefix: str = "test", subdir: Optional[str] = None) -> Optional[str]:
    """
    Stop Appium screen recording and save to evidence/recordings/.
    Returns the file path if successful, else None.
    """
    ensure_dirs()
    out_dir = RECORDINGS_DIR / subdir if subdir else RECORDINGS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        payload = driver.stop_recording_screen()
        ts = int(time.time() * 1000)
        name = f"{prefix}_{ts}.mp4"
        path = out_dir / name
        path.write_bytes(base64.b64decode(payload))
        return str(path.resolve())
    except Exception:
        return None
