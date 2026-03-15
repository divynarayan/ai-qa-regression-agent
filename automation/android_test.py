"""
Android regression test: Settings → Wi-Fi, screenshot, return PASS/FAIL.
Run with: python -m automation.android_test
Requires Appium server and Android emulator.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_SCREENSHOTS = PROJECT_ROOT / "reports" / "screenshots"
REPORTS_RECORDINGS = PROJECT_ROOT / "reports" / "recordings"
APPIUM_URL = "http://127.0.0.1:4723"


def run_test() -> str:
    """Run Android Settings → Wi-Fi test. Returns 'PASS' or 'FAIL'."""
    try:
        from appium import webdriver
        from appium.options.android import UiAutomator2Options
        from appium.webdriver.common.appiumby import AppiumBy
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        import time
    except ImportError:
        print("FAIL: appium-python-client not installed", file=sys.stderr)
        return "FAIL"

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.device_name = "Android Emulator"
    options.automation_name = "UiAutomator2"
    options.app_package = "com.android.settings"
    options.app_activity = "com.android.settings.Settings"

    driver = None
    try:
        driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
        wait = WebDriverWait(driver, timeout=15)
        wifi_sel = 'new UiSelector().textContains("Wi").className("android.widget.TextView")'
        wifi = wait.until(
            EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, wifi_sel))
        )
        wifi.click()
        time.sleep(2)
        REPORTS_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        path = REPORTS_SCREENSHOTS / "android_wifi_settings.png"
        driver.save_screenshot(str(path))
        return "PASS"
    except Exception as e:
        print(str(e), file=sys.stderr)
        if driver:
            try:
                REPORTS_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
                driver.save_screenshot(str(REPORTS_SCREENSHOTS / "android_wifi_error.png"))
            except Exception:
                pass
        return "FAIL"
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    result = run_test()
    print(result)  # Dashboard parses stdout for PASS/FAIL
    sys.exit(0 if result == "PASS" else 1)
