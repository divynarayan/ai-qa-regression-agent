"""
Android regression test: launch Settings → Wi-Fi, capture screenshot and recording, return PASS/FAIL.
Uses UiAutomator2 and Appium. Evidence saved under evidence/screenshots and evidence/recordings.
"""

import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import (
    ANDROID_SETTINGS_ACTIVITY,
    ANDROID_SETTINGS_PACKAGE,
    APPIUM_URL,
    ANDROID_DEVICE_NAME,
    ANDROID_PLATFORM_VERSION,
    ensure_dirs,
)
from utils.recording import start_recording, stop_recording
from utils.screenshot import save_screenshot


def run_android_test(test_name: str = "android_wifi_test") -> dict:
    """
    Execute Android Settings → Wi-Fi test. Returns a result dict:
    {
        "test_name": str,
        "platform": "Android",
        "status": "PASS" | "FAIL",
        "screenshot": str | None,
        "video": str | None,
        "error": str | None,
    }
    """
    ensure_dirs()
    result = {
        "test_name": test_name,
        "platform": "Android",
        "status": "FAIL",
        "screenshot": None,
        "video": None,
        "error": None,
    }

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.device_name = ANDROID_DEVICE_NAME
    options.platform_version = ANDROID_PLATFORM_VERSION
    options.automation_name = "UiAutomator2"
    options.app_package = ANDROID_SETTINGS_PACKAGE
    options.app_activity = ANDROID_SETTINGS_ACTIVITY

    driver = None
    try:
        driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
        wait = WebDriverWait(driver, timeout=15)

        start_recording(driver)

        # Navigate to Wi-Fi (text may vary: "Wi‑Fi", "Wifi", "Wi-Fi")
        wifi_selector = 'new UiSelector().textContains("Wi").className("android.widget.TextView")'
        wifi = wait.until(
            EC.presence_of_element_located(
                (AppiumBy.ANDROID_UIAUTOMATOR, wifi_selector)
            )
        )
        wifi.click()
        time.sleep(2)

        result["screenshot"] = save_screenshot(driver, prefix=test_name, subdir="android")
        result["video"] = stop_recording(driver, prefix=test_name, subdir="android")
        result["status"] = "PASS"
    except Exception as e:
        result["error"] = str(e)
        if driver:
            try:
                result["screenshot"] = save_screenshot(
                    driver, prefix=f"{test_name}_error", subdir="android"
                )
                result["video"] = stop_recording(driver, prefix=test_name, subdir="android")
            except Exception:
                pass
    finally:
        if driver:
            driver.quit()

    return result
