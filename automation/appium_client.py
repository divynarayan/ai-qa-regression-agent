from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from appium import webdriver


SCREENSHOTS_DIR = Path("reports") / "screenshots"
LOGS_DIR = Path("reports") / "logs"

SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AppiumConfig:
    platform_name: str  # "Android" or "iOS"
    device_name: str
    appium_server_url: str = "http://127.0.0.1:4723"
    platform_version: Optional[str] = None
    app_package: Optional[str] = None  # Android
    app_activity: Optional[str] = None  # Android
    bundle_id: Optional[str] = None  # iOS

    def desired_capabilities(self) -> Dict[str, Any]:
        caps: Dict[str, Any] = {
            "platformName": self.platform_name,
            "deviceName": self.device_name,
            "automationName": "UiAutomator2" if self.platform_name == "Android" else "XCUITest",
        }
        if self.platform_version:
            caps["platformVersion"] = self.platform_version
        if self.app_package:
            caps["appPackage"] = self.app_package
        if self.app_activity:
            caps["appActivity"] = self.app_activity
        if self.bundle_id:
            caps["bundleId"] = self.bundle_id
        return caps


class AppiumSession:
    def __init__(self, config: AppiumConfig) -> None:
        self.config = config
        self.driver: Optional[webdriver.Remote] = None

    def __enter__(self) -> "AppiumSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self.driver is not None:
            return
        self.driver = webdriver.Remote(
            command_executor=self.config.appium_server_url,
            desired_capabilities=self.config.desired_capabilities(),
        )

    def stop(self) -> None:
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

    def screenshot(self, prefix: str) -> str:
        if not self.driver:
            raise RuntimeError("Driver not started")
        ts = int(time.time() * 1000)
        filename = f"{prefix}_{ts}.png"
        path = SCREENSHOTS_DIR / filename
        self.driver.get_screenshot_as_file(str(path))
        return str(path)

    def save_log(self, name: str, content: str) -> str:
        ts = int(time.time() * 1000)
        filename = f"{name}_{ts}.log"
        path = LOGS_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(path)

