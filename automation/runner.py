from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Literal

from ai_engine.bug_parser import TestPlan, TestStep
from automation.appium_client import AppiumConfig, AppiumSession
from reports.storage import save_report


Platform = Literal["android", "ios"]


@dataclass
class StepResult:
    step_number: int
    description: str
    status: Literal["PASS", "FAIL"]
    error: str | None = None
    screenshot_path: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunResult:
    plan_id: str
    platform: Platform
    overall_status: Literal["PASS", "FAIL"]
    step_results: List[StepResult]
    report_path: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "platform": self.platform,
            "overall_status": self.overall_status,
            "step_results": [s.to_dict() for s in self.step_results],
            "report_path": self.report_path,
        }


def _default_android_config() -> AppiumConfig:
    return AppiumConfig(
        platform_name="Android",
        device_name="Android Emulator",
        app_package="com.example.app",
        app_activity=".MainActivity",
    )


def _default_ios_config() -> AppiumConfig:
    return AppiumConfig(
        platform_name="iOS",
        device_name="iPhone 17 Pro",
        bundle_id="com.example.app",
    )


def _execute_step(session: AppiumSession, step: TestStep, platform: Platform) -> None:
    """
    Translate a generic TestStep into Appium actions.

    NOTE: This is a highly simplified placeholder. In a real project, you would
    map step.target to concrete locators and implement click/input/assert logic.
    """
    driver = session.driver
    if not driver:
        raise RuntimeError("Driver not started")

    # Placeholder: for now we just log the description using driver.log_types if available.
    # This keeps the skeleton safe and side-effect free.
    _ = platform  # reserved for platform-specific branching
    _ = step
    # Real implementation would go here.


def run_regression_on_platform(plan: TestPlan, platform: Platform) -> RunResult:
    config = _default_android_config() if platform == "android" else _default_ios_config()
    step_results: List[StepResult] = []

    with AppiumSession(config) as session:
        for step in plan.steps:
            try:
                _execute_step(session, step, platform)
                screenshot = session.screenshot(f"{plan.id}_{platform}_step{step.step_number}")
                step_results.append(
                    StepResult(
                        step_number=step.step_number,
                        description=step.description,
                        status="PASS",
                        error=None,
                        screenshot_path=screenshot,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                screenshot = None
                try:
                    screenshot = session.screenshot(
                        f"{plan.id}_{platform}_step{step.step_number}_error"
                    )
                except Exception:  # noqa: BLE001
                    # If screenshot fails, continue without it.
                    pass

                step_results.append(
                    StepResult(
                        step_number=step.step_number,
                        description=step.description,
                        status="FAIL",
                        error=str(exc),
                        screenshot_path=screenshot,
                    )
                )

    overall = "FAIL" if any(s.status == "FAIL" for s in step_results) else "PASS"

    report_data = {
        "plan": plan.to_dict(),
        "platform": platform,
        "overall_status": overall,
        "steps": [s.to_dict() for s in step_results],
    }
    report_path = save_report(plan.id, platform, report_data)

    return RunResult(
        plan_id=plan.id,
        platform=platform,
        overall_status=overall,
        step_results=step_results,
        report_path=report_path,
    )

