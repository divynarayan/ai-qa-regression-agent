"""
Screenshot capture utilities. Saves images under evidence/screenshots/.
"""

import base64
from pathlib import Path
from typing import Optional

from config.settings import SCREENSHOTS_DIR, ensure_dirs


def save_screenshot(driver, prefix: str, subdir: Optional[str] = None) -> str:
    """
    Capture screenshot from Appium driver and save to evidence/screenshots/.
    Returns the absolute path of the saved file.
    """
    ensure_dirs()
    out_dir = SCREENSHOTS_DIR / subdir if subdir else SCREENSHOTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    import time
    ts = int(time.time() * 1000)
    name = f"{prefix}_{ts}.png"
    path = out_dir / name

    png = driver.get_screenshot_as_png()
    path.write_bytes(png)
    return str(path.resolve())


def save_screenshot_from_base64(base64_data: str, prefix: str, subdir: Optional[str] = None) -> str:
    """Save a base64-encoded PNG (e.g. from Appium recording) to evidence/screenshots/."""
    ensure_dirs()
    out_dir = SCREENSHOTS_DIR / subdir if subdir else SCREENSHOTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    import time
    ts = int(time.time() * 1000)
    name = f"{prefix}_{ts}.png"
    path = out_dir / name

    path.write_bytes(base64.b64decode(base64_data))
    return str(path.resolve())
