"""
Test execution engine: reads structured test steps, translates them to Appium commands,
executes on simulator/emulator, and returns PASS/FAIL with evidence paths.
Uses WebDriverWait and retries for stability. Integrates with utils/evidence and logging.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

APPIUM_URL = "http://127.0.0.1:4723"
ELEMENT_WAIT_TIMEOUT = 15
MAX_RETRIES = 3


def _get_logger():
    import logging
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "test_execution.log"
    logger = logging.getLogger("test_execution")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    return logger


def _find_element_ios(driver, wait, target: str):
    """Resolve target to an iOS element with retries. Uses XCUITest locators."""
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    # Normalize target for common cases
    t = target.strip().lower()
    if t in ("wifi", "wi-fi", "wi fi"):
        # Try accessibility id first, then predicate
        for loc in [
            (AppiumBy.ACCESSIBILITY_ID, "Wi-Fi"),
            (AppiumBy.IOS_PREDICATE, "label CONTAINS 'Wi'"),
        ]:
            try:
                return wait.until(EC.presence_of_element_located(loc))
            except Exception:
                continue
    if t == "wifi screen":
        return wait.until(EC.presence_of_element_located((AppiumBy.IOS_PREDICATE, "label CONTAINS 'Wi'")))
    # Generic: treat target as label text
    return wait.until(EC.presence_of_element_located((AppiumBy.IOS_PREDICATE, f"label CONTAINS '{target}'")))


def _find_element_android(driver, wait, target: str):
    """Resolve target to an Android element with retries."""
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    t = target.strip().lower()
    if t in ("wifi", "wi-fi", "wi fi", "wifi screen"):
        sel = 'new UiSelector().textContains("Wi").className("android.widget.TextView")'
        return wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, sel)))
    sel = f'new UiSelector().textContains("{target}").className("android.widget.TextView")'
    return wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, sel)))


def _execute_steps_ios(
    driver,
    steps: List[Dict[str, Any]],
    evidence_prefix: str,
) -> tuple[str, Optional[str], Optional[str]]:
    """Execute structured steps on iOS. Returns (status, screenshot_path, video_path)."""
    from selenium.webdriver.support.ui import WebDriverWait
    from utils.evidence import capture_screenshot, start_recording, stop_recording

    wait = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT)
    log = _get_logger()
    screenshot_path: Optional[str] = None
    video_path: Optional[str] = None

    for i, step in enumerate(steps):
        action = (step.get("action") or "").strip().lower()
        target = (step.get("target") or "").strip()
        log.info(f"iOS step {i+1}: action={action}, target={target}")

        try:
            if action == "open_app":
                # Already opened by capability (bundle_id). If target is settings, no-op.
                if target.lower() == "settings":
                    pass
                else:
                    log.info(f"open_app target={target} (no-op for now)")
            elif action == "start_recording":
                start_recording(driver)
            elif action == "stop_recording":
                video_path = stop_recording(driver, prefix=evidence_prefix, subdir="ios")
            elif action == "tap":
                for attempt in range(MAX_RETRIES):
                    try:
                        el = _find_element_ios(driver, wait, target or "Wi-Fi")
                        el.click()
                        time.sleep(1)
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(0.5)
                        else:
                            raise e
            elif action == "scroll":
                driver.execute_script("mobile: scroll", {"direction": "down"})
                time.sleep(0.5)
            elif action == "verify_element":
                _find_element_ios(driver, wait, target or "WiFi Screen")
            elif action == "capture_screenshot":
                screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="ios")
            else:
                log.warning(f"Unknown action: {action}")
        except Exception as e:
            log.exception(f"Step failed: {e}")
            try:
                screenshot_path = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir="ios")
            except Exception:
                pass
            return "FAIL", screenshot_path, video_path

    if not screenshot_path and steps:
        try:
            screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="ios")
        except Exception:
            pass
    return "PASS", screenshot_path, video_path


def _execute_steps_android(
    driver,
    steps: List[Dict[str, Any]],
    evidence_prefix: str,
) -> tuple[str, Optional[str], Optional[str]]:
    """Execute structured steps on Android. Returns (status, screenshot_path, video_path)."""
    from selenium.webdriver.support.ui import WebDriverWait
    from utils.evidence import capture_screenshot, start_recording, stop_recording

    wait = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT)
    log = _get_logger()
    screenshot_path: Optional[str] = None
    video_path: Optional[str] = None

    for i, step in enumerate(steps):
        action = (step.get("action") or "").strip().lower()
        target = (step.get("target") or "").strip()
        log.info(f"Android step {i+1}: action={action}, target={target}")

        try:
            if action == "open_app":
                pass  # Already launched via app_package/activity
            elif action == "start_recording":
                start_recording(driver)
            elif action == "stop_recording":
                video_path = stop_recording(driver, prefix=evidence_prefix, subdir="android")
            elif action == "tap":
                for attempt in range(MAX_RETRIES):
                    try:
                        el = _find_element_android(driver, wait, target or "WiFi")
                        el.click()
                        time.sleep(1)
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(0.5)
                        else:
                            raise e
            elif action == "scroll":
                driver.execute_script("mobile: scrollGesture", {"left": 100, "top": 100, "width": 200, "height": 400, "direction": "down", "percent": 1.0})
            elif action == "verify_element":
                _find_element_android(driver, wait, target or "WiFi Screen")
            elif action == "capture_screenshot":
                screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="android")
            else:
                log.warning(f"Unknown action: {action}")
        except Exception as e:
            log.exception(f"Step failed: {e}")
            try:
                screenshot_path = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir="android")
            except Exception:
                pass
            return "FAIL", screenshot_path, video_path

    if not screenshot_path and steps:
        try:
            screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="android")
        except Exception:
            pass
    return "PASS", screenshot_path, video_path


def run_structured_test(
    platform: str,
    steps: List[Dict[str, Any]],
    bug_description: str = "",
) -> Dict[str, Any]:
    """
    Run structured test steps on iOS or Android. Returns a result dict for the dashboard and report:
    {
        "timestamp": "...",
        "platform": "iOS" | "Android",
        "bug_description": "...",
        "status": "PASS" | "FAIL",
        "screenshot": path or None,
        "video": path or None,
        "error": message or None,
    }
    """
    import logging
    from datetime import datetime
    from appium import webdriver
    from appium.options.ios import XCUITestOptions
    from appium.options.android import UiAutomator2Options
    from utils.evidence import start_recording, stop_recording

    log = _get_logger()
    ts = datetime.utcnow().isoformat() + "Z"
    result = {
        "timestamp": ts,
        "platform": platform,
        "bug_description": bug_description,
        "status": "FAIL",
        "screenshot": None,
        "video": None,
        "error": None,
    }
    evidence_prefix = f"run_{int(time.time())}"

    if not steps:
        result["error"] = "No steps to execute"
        return result

    driver = None
    try:
        if platform.lower() == "ios":
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.device_name = "iPhone 16e"
            options.platform_version = "26.3"
            options.automation_name = "XCUITest"
            options.bundle_id = "com.apple.Preferences"
            driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
            start_recording(driver)
            status, screenshot_path, video_path = _execute_steps_ios(driver, steps, evidence_prefix)
            result["video"] = video_path or stop_recording(driver, prefix=evidence_prefix, subdir="ios")
        else:
            options = UiAutomator2Options()
            options.platform_name = "Android"
            options.device_name = "Android Emulator"
            options.automation_name = "UiAutomator2"
            options.app_package = "com.android.settings"
            options.app_activity = "com.android.settings.Settings"
            driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
            start_recording(driver)
            status, screenshot_path, video_path = _execute_steps_android(driver, steps, evidence_prefix)
            result["video"] = video_path or stop_recording(driver, prefix=evidence_prefix, subdir="android")

        result["status"] = status
        result["screenshot"] = screenshot_path
    except Exception as e:
        log.exception(str(e))
        result["error"] = str(e)
        if driver:
            try:
                from utils.evidence import capture_screenshot
                result["screenshot"] = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir=platform.lower())
                result["video"] = stop_recording(driver, prefix=evidence_prefix, subdir=platform.lower())
            except Exception:
                pass
    finally:
        if driver:
            driver.quit()

    return result
