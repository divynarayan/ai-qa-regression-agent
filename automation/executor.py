"""
Test execution engine: reads structured test steps, translates them to Appium commands,
executes on simulator/emulator, and returns PASS/FAIL with evidence paths.
Uses WebDriverWait and retries for stability. Integrates with utils/evidence and logging.
Also used by the chat-driven AI QA agent, which passes a BUG ID to name evidence files.
"""


import os
import shutil
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

    if not (target or "").strip():
        raise ValueError("Target is required for element lookup")

    pred = (AppiumBy.IOS_PREDICATE, f"label CONTAINS '{target}'")

    # Prefer a visible element if multiple match.
    def _visible_predicate(_driver):
        els = _driver.find_elements(*pred)
        for el in els:
            try:
                if el.is_displayed():
                    return el
            except Exception:
                continue
        return False

    try:
        return wait.until(_visible_predicate)
    except Exception:
        # If not found, auto-scroll and retry (best-effort; no static flows).
        try:
            driver.execute_script("mobile: scroll", {"direction": "down"})
        except Exception:
            pass
        return wait.until(_visible_predicate)


def _find_element_android(driver, wait, target: str):
    """Resolve target to an Android element with retries."""
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    if not (target or "").strip():
        raise ValueError("Target is required for element lookup")

    sel = (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{target}")')

    def _visible_predicate(_driver):
        els = _driver.find_elements(*sel)
        for el in els:
            try:
                if el.is_displayed():
                    return el
            except Exception:
                continue
        return False

    try:
        return wait.until(_visible_predicate)
    except Exception:
        # Auto-scroll gesture then retry.
        try:
            driver.execute_script(
                "mobile: scrollGesture",
                {"left": 100, "top": 100, "width": 400, "height": 800, "direction": "down", "percent": 0.8},
            )
        except Exception:
            pass
        return wait.until(_visible_predicate)


def _dismiss_system_alerts_ios(driver) -> None:
    """
    Best-effort dismissal of common iOS system alerts.
    """
    try:
        from appium.webdriver.common.appiumby import AppiumBy
        labels = ["Allow", "OK", "Continue", "While Using the App", "Don’t Allow", "Don't Allow"]
        for lbl in labels:
            els = driver.find_elements(AppiumBy.ACCESSIBILITY_ID, lbl)
            if els:
                try:
                    els[0].click()
                    return
                except Exception:
                    continue
    except Exception:
        return


def _dismiss_system_alerts_android(driver) -> None:
    """
    Best-effort dismissal of common Android runtime permission dialogs.
    """
    try:
        from appium.webdriver.common.appiumby import AppiumBy
        candidates = [
            "Allow",
            "ALLOW",
            "OK",
            "Continue",
            "While using the app",
        ]
        for text in candidates:
            els = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{text}")')
            if els:
                try:
                    els[0].click()
                    return
                except Exception:
                    continue
    except Exception:
        return


def _find_field_ios(driver, wait, field: str):
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    f = field.strip()
    # Try accessibility id or "value" / "label" contains.
    for loc in [
        (AppiumBy.ACCESSIBILITY_ID, f),
        (AppiumBy.IOS_PREDICATE, f"name CONTAINS '{f}' OR label CONTAINS '{f}'"),
        (AppiumBy.IOS_PREDICATE, f"type == 'XCUIElementTypeTextField' AND (name CONTAINS '{f}' OR label CONTAINS '{f}')"),
        (AppiumBy.IOS_PREDICATE, f"type == 'XCUIElementTypeSecureTextField' AND (name CONTAINS '{f}' OR label CONTAINS '{f}')"),
    ]:
        try:
            return wait.until(EC.presence_of_element_located(loc))
        except Exception:
            continue
    return wait.until(EC.presence_of_element_located((AppiumBy.IOS_PREDICATE, f"label CONTAINS '{f}'")))


def _find_field_android(driver, wait, field: str):
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    f = field.strip()
    selectors = [
        f'new UiSelector().textContains("{f}")',
        f'new UiSelector().descriptionContains("{f}")',
        f'new UiSelector().resourceIdMatches(".*{f}.*")',
    ]
    for sel in selectors:
        try:
            return wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, sel)))
        except Exception:
            continue
    return wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{f}")')))


def _resolve_target(step: Dict[str, Any], elements: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    If YAML uses an element key (e.g. login_button), resolve it to its display value.
    Keeps backwards compatibility with steps that already use literal text targets.
    """
    if not elements:
        return step
    tgt = step.get("target")
    if isinstance(tgt, str) and tgt in elements and isinstance(elements.get(tgt), dict):
        resolved = dict(step)
        resolved["_element"] = elements[tgt]
        # For existing locator logic we keep `target` as the human-facing label/value.
        resolved["target"] = elements[tgt].get("value") or tgt
        # For input actions, map to `field`.
        if resolved.get("action") == "input":
            resolved["field"] = elements[tgt].get("value") or tgt
        return resolved
    return step

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
        print(f"Running step: {step}")
        action = (step.get("action") or "").strip().lower()
        target = (step.get("target") or "").strip()
        log.info(f"iOS step {i+1}: action={action}, target={target}")

        try:
            _dismiss_system_alerts_ios(driver)
            if action == "open_app":
                log.info("open_app (no-op; start from home screen / current app)")
            elif action == "start_recording":
                start_recording(driver)
            elif action == "stop_recording":
                video_path = stop_recording(driver, prefix=evidence_prefix, subdir="ios")
            elif action == "tap":
                if not target:
                    raise ValueError("Target is required for tap")
                for attempt in range(MAX_RETRIES):
                    try:
                        el = _find_element_ios(driver, wait, target)
                        el.click()
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            pass
                        else:
                            # Last-chance scroll before failing
                            try:
                                driver.execute_script("mobile: scroll", {"direction": "down"})
                            except Exception:
                                pass
                            raise e
            elif action == "input":
                field = (step.get("field") or target or "").strip()
                value = str(step.get("value") or "")
                if not field:
                    raise ValueError("input action requires `field` (or `target`).")
                el = _find_field_ios(driver, wait, field)
                try:
                    el.clear()
                except Exception:
                    pass
                el.send_keys(value)
            elif action == "scroll":
                driver.execute_script("mobile: scroll", {"direction": "down"})
            elif action == "verify_element":
                if not target:
                    raise ValueError("Target is required for verify_element")
                _find_element_ios(driver, wait, target)
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
        print(f"Running step: {step}")
        action = (step.get("action") or "").strip().lower()
        target = (step.get("target") or "").strip()
        log.info(f"Android step {i+1}: action={action}, target={target}")

        try:
            _dismiss_system_alerts_android(driver)
            if action == "open_app":
                log.info("open_app (no-op; start from home screen / current app)")
            elif action == "start_recording":
                start_recording(driver)
            elif action == "stop_recording":
                video_path = stop_recording(driver, prefix=evidence_prefix, subdir="android")
            elif action == "tap":
                if not target:
                    raise ValueError("Target is required for tap")
                for attempt in range(MAX_RETRIES):
                    try:
                        el = _find_element_android(driver, wait, target)
                        el.click()
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            pass
                        else:
                            # Last-chance scroll before failing
                            try:
                                driver.execute_script("mobile: scroll", {"direction": "down"})
                            except Exception:
                                pass
                            raise e
            elif action == "input":
                field = (step.get("field") or target or "").strip()
                value = str(step.get("value") or "")
                if not field:
                    raise ValueError("input action requires `field` (or `target`).")
                el = _find_field_android(driver, wait, field)
                try:
                    el.click()
                except Exception:
                    pass
                try:
                    el.clear()
                except Exception:
                    pass
                el.send_keys(value)
            elif action == "scroll":
                driver.execute_script("mobile: scrollGesture", {"left": 100, "top": 100, "width": 200, "height": 400, "direction": "down", "percent": 1.0})
            elif action == "verify_element":
                if not target:
                    raise ValueError("Target is required for verify_element")
                _find_element_android(driver, wait, target)
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
    bug_id: Optional[str] = None,
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
    result: Dict[str, Any] = {
        "timestamp": ts,
        "platform": platform,
        "bug_description": bug_description,
        "status": "FAIL",
        "screenshot": None,
        "video": None,
        "error": None,
    }
    evidence_prefix = bug_id or f"run_{int(time.time())}"

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
            # Launch the real app under test.
            options.bundle_id = "com.cwp.app"
            driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
            time.sleep(3)
            # Start recording before first step (chat agent + manual flows).
            start_recording(driver)
            status, screenshot_path, video_path = _execute_steps_ios(driver, steps, evidence_prefix)
            result["video"] = video_path or stop_recording(driver, prefix=evidence_prefix, subdir="ios")
        else:
            options = UiAutomator2Options()
            options.platform_name = "Android"
            options.device_name = "Android Emulator"
            options.automation_name = "UiAutomator2"
            # Launch the real app under test.
            options.app_package = "com.cwp.app"
            options.app_activity = "com.cwp.app.MainActivity"
            driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
            time.sleep(3)
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


def _copy_evidence_for_bug(
    bug_id: str,
    screenshot_path: Optional[str],
    video_path: Optional[str],
) -> Dict[str, Optional[str]]:
    """
    Copy generic evidence files into BUG-specific names, e.g.:
    evidence/screenshots/BUG-12345.png
    evidence/recordings/BUG-12345.mp4
    """
    if not bug_id:
        return {"screenshot_bug": None, "video_bug": None}

    from utils.evidence import EVIDENCE_SCREENSHOTS, EVIDENCE_RECORDINGS, _ensure_dirs

    _ensure_dirs()
    os.makedirs(EVIDENCE_SCREENSHOTS, exist_ok=True)
    os.makedirs(EVIDENCE_RECORDINGS, exist_ok=True)

    screenshot_bug: Optional[str] = None
    video_bug: Optional[str] = None

    if screenshot_path and Path(screenshot_path).exists():
        dest = EVIDENCE_SCREENSHOTS / f"{bug_id}.png"
        shutil.copyfile(screenshot_path, dest)
        screenshot_bug = str(dest.resolve())

    if video_path and Path(video_path).exists():
        dest = EVIDENCE_RECORDINGS / f"{bug_id}.mp4"
        shutil.copyfile(video_path, dest)
        video_bug = str(dest.resolve())

    return {"screenshot_bug": screenshot_bug, "video_bug": video_bug}


def run_test_case(
    test_case: Dict[str, Any],
    test_data: Optional[Dict[str, Any]] = None,
    bug_id: Optional[str] = None,
    platform: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a YAML-style test case object + JSON test data object.
    This is used by the dashboard upload flow.
    - Reads platform configuration from `ai_qa_agent/config/app_config.yaml` when present.
    - Substitutes variables like `{{phone_number}}` using provided test_data.
    - Delegates execution to `run_structured_test` with parsed steps.
    """
    import yaml

    test_data = test_data or {}

    # Prefer the new production-style config under ai_qa_agent/ if it exists,
    # unless the caller explicitly overrides the platform (chat agent).
    if platform is None:
        cfg_path = PROJECT_ROOT / "ai_qa_agent" / "config" / "app_config.yaml"
        platform = "iOS"
        if cfg_path.exists():
            try:
                cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                p = str(cfg.get("platform", "ios")).strip().lower()
                platform = "iOS" if p == "ios" else "Android"
            except Exception:
                platform = "iOS"

    # Parse and substitute variables using the new engine if available.
    steps = test_case.get("steps", [])
    try:
        from ai_qa_agent.ai_engine.step_parser import parse_steps
        steps = parse_steps(test_case, test_data)
    except Exception:
        # Fallback: raw steps with no substitution (keeps existing system resilient)
        if not isinstance(steps, list):
            raise ValueError("test_case.steps must be a list")

    # If the YAML includes an `elements` section, resolve element keys to labels.
    elements = test_case.get("elements")
    if isinstance(elements, dict):
        steps = [_resolve_target(s, elements) if isinstance(s, dict) else s for s in steps]  # type: ignore[list-item]

    bug_desc = str(test_case.get("id", ""))
    result = run_structured_test(platform, steps, bug_description=bug_desc, bug_id=bug_id)
    result["test_case"] = test_case.get("id")
    if bug_id:
        # Copy evidence into BUG-specific filenames for the chat-driven agent.
        bug_paths = _copy_evidence_for_bug(bug_id, result.get("screenshot"), result.get("video"))
        result.update(bug_paths)
        result["bug_id"] = bug_id
    return result
