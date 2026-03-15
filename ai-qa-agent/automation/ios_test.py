"""
iOS regression test: open Settings → Wi-Fi, capture screenshot and recording, return PASS/FAIL.
Uses XCUITest and Appium. Evidence saved under evidence/screenshots and evidence/recordings.
"""

import sys
import time
from pathlib import Path

# Ensure project root is on path when run as script
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import (
    APPIUM_URL,
    IOS_BUNDLE_ID_SETTINGS,
    IOS_DEVICE_NAME,
    IOS_PLATFORM_VERSION,
    ensure_dirs,
)
from utils.recording import start_recording, stop_recording
from utils.screenshot import save_screenshot


def run_ios_test(test_name: str = "ios_wifi_test") -> dict:
    """
    Execute iOS Settings → Wi-Fi test. Returns a result dict suitable for regression_report:
    {
        "test_name": str,
        "platform": "iOS",
        "status": "PASS" | "FAIL",
        "screenshot": str | None,
        "video": str | None,
        "error": str | None,
    }
    """
    ensure_dirs()
    result = {
        "test_name": test_name,
        "platform": "iOS",
        "status": "FAIL",
        "screenshot": None,
        "video": None,
        "error": None,
    }

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.device_name = IOS_DEVICE_NAME
    options.platform_version = IOS_PLATFORM_VERSION
    options.automation_name = "XCUITest"
    options.bundle_id = IOS_BUNDLE_ID_SETTINGS

    driver = None
    try:
        driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
        wait = WebDriverWait(driver, timeout=15)

        start_recording(driver)

        # Navigate to Wi-Fi
        wifi_cell = wait.until(
            EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Wi-Fi"))
        )
        wifi_cell.click()
        time.sleep(2)

        result["screenshot"] = save_screenshot(driver, prefix=test_name, subdir="ios")
        result["video"] = stop_recording(driver, prefix=test_name, subdir="ios")
        result["status"] = "PASS"
    except Exception as e:
        result["error"] = str(e)
        if driver:
            try:
                result["screenshot"] = save_screenshot(
                    driver, prefix=f"{test_name}_error", subdir="ios"
                )
                result["video"] = stop_recording(driver, prefix=test_name, subdir="ios")
            except Exception:
                pass
    finally:
        if driver:
            driver.quit()

    return result
