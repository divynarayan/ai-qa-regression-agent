"""
Appium automation for iOS Simulator: open Settings → Wi-Fi → screenshot → PASS/FAIL.

Run with: python ios_test.py
Requires:
- Appium server running at http://127.0.0.1:4723
- iOS Simulator booted (e.g. iPhone 17 Pro)
"""

import sys
import time
from pathlib import Path

from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ------------------------------
# CONFIGURATION
# ------------------------------

APPIUM_URL = "http://127.0.0.1:4723"

# UPDATE IF NEEDED → change device name if your simulator is different
DEVICE_NAME = "iPhone 17 Pro"

# UPDATE IF NEEDED → change iOS version if your simulator is different
IOS_VERSION = "26.3"

SCREENSHOT_PATH = Path("reports/screenshots/ios_wifi_settings.png")


# ------------------------------
# TEST FUNCTION
# ------------------------------

def run_test() -> str:
    """Open Settings → Wi-Fi → screenshot. Returns 'PASS' or 'FAIL'."""

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.platform_version = IOS_VERSION
    options.device_name = DEVICE_NAME
    options.automation_name = "XCUITest"

    # Opens the Settings app automatically
    options.bundle_id = "com.apple.Preferences"

    driver = webdriver.Remote(
        command_executor=APPIUM_URL,
        options=options
    )

    wait = WebDriverWait(driver, timeout=15)

    try:

        print("Connected to iOS simulator!")

        # ------------------------------
        # STEP 1: Locate Wi-Fi cell
        # ------------------------------

        try:
            wifi_cell = wait.until(
                EC.presence_of_element_located(
                    (AppiumBy.IOS_PREDICATE, "label CONTAINS 'Wi'")
                )
            )
        except:
            # Scroll down if Wi-Fi is not immediately visible
            driver.execute_script("mobile: swipe", {"direction": "down"})
            wifi_cell = wait.until(
                EC.presence_of_element_located(
                    (AppiumBy.IOS_PREDICATE, "label CONTAINS 'Wi'")
                )
            )

        # ------------------------------
        # STEP 2: Tap Wi-Fi
        # ------------------------------

        wifi_cell.click()

        # Wait for Wi-Fi screen to load
        time.sleep(2)

        # ------------------------------
        # STEP 3: Take Screenshot
        # ------------------------------

        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(SCREENSHOT_PATH))

        print("Screenshot captured!")

        return "PASS"

    except Exception as e:

        print(f"Error: {e}", file=sys.stderr)

        # Save screenshot on failure
        try:
            SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            driver.save_screenshot(
                str(SCREENSHOT_PATH.parent / "ios_wifi_error.png")
            )
        except:
            pass

        return "FAIL"

    finally:
        driver.quit()


# ------------------------------
# MAIN ENTRY
# ------------------------------

def main():
    result = run_test()
    print(result)
    sys.exit(0 if result == "PASS" else 1)


if __name__ == "__main__":
    main()