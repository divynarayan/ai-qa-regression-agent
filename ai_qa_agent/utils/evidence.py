from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .logger import get_logger

log = get_logger(__name__)


def _agent_root() -> Path:
    # ai_qa_agent/utils/evidence.py -> ai_qa_agent
    return Path(__file__).resolve().parents[1]


def _safe_filename(prefix: str, ext: str) -> str:
    ts = int(time.time() * 1000)
    return f"{prefix}_{ts}.{ext}"


@dataclass(frozen=True)
class EvidencePaths:
    screenshots_dir: Path
    recordings_dir: Path


def ensure_evidence_dirs() -> EvidencePaths:
    root = _agent_root()
    screenshots_dir = root / "evidence" / "screenshots"
    recordings_dir = root / "evidence" / "recordings"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return EvidencePaths(screenshots_dir=screenshots_dir, recordings_dir=recordings_dir)


def capture_screenshot(driver, prefix: str = "screenshot") -> Optional[str]:
    paths = ensure_evidence_dirs()
    out = paths.screenshots_dir / _safe_filename(prefix, "png")
    try:
        driver.get_screenshot_as_file(str(out))
        log.info(f"Captured screenshot: {out}")
        return str(out)
    except Exception as e:
        log.exception(f"Failed to capture screenshot: {e}")
        return None


def start_recording(driver) -> bool:
    try:
        driver.start_recording_screen()
        log.info("Started screen recording.")
        return True
    except Exception as e:
        log.exception(f"Failed to start recording: {e}")
        return False


def stop_recording(driver, prefix: str = "recording") -> Optional[str]:
    paths = ensure_evidence_dirs()
    out = paths.recordings_dir / _safe_filename(prefix, "mp4")
    try:
        payload_b64 = driver.stop_recording_screen()
        if not payload_b64:
            return None
        raw = base64.b64decode(payload_b64)
        out.write_bytes(raw)
        log.info(f"Saved recording: {out}")
        return str(out)
    except Exception as e:
        log.exception(f"Failed to stop/save recording: {e}")
        return None

