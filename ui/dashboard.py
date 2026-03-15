"""
AI QA Regression Testing Agent — production dashboard.
Flow: Bug description → Generate structured test steps (JSON) → Run iOS/Android via executor →
      Capture evidence → PASS/FAIL + screenshot/video. Sidebar: system status. Last 5 runs in history.
"""

import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_SCREENSHOTS = PROJECT_ROOT / "reports" / "screenshots"
REPORTS_RECORDINGS = PROJECT_ROOT / "reports" / "recordings"
EVIDENCE_SCREENSHOTS = PROJECT_ROOT / "evidence" / "screenshots"
EVIDENCE_RECORDINGS = PROJECT_ROOT / "evidence" / "recordings"
APPIUM_URL = "http://127.0.0.1:4723"


def check_appium_running() -> bool:
    try:
        import urllib.request
        req = urllib.request.urlopen(f"{APPIUM_URL}/status", timeout=2)
        return req.status == 200
    except Exception:
        return False


def check_ios_simulator_connected() -> bool:
    try:
        proc = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "booted"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0 and "Booted" in (proc.stdout or "")
    except Exception:
        return False


def check_android_emulator_connected() -> bool:
    try:
        proc = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = (proc.stdout or "") or ""
        lines = [l for l in out.splitlines() if "device" in l and "emulator" in l or "\tdevice" in l]
        return len(lines) >= 1
    except Exception:
        return False


def main() -> None:
    st.set_page_config(
        page_title="AI QA Regression Testing Agent",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ----- Sidebar: System Status (green indicators) -----
    with st.sidebar:
        st.header("System Status")
        appium_ok = check_appium_running()
        st.markdown(f"**Appium Server:** {'Running' if appium_ok else 'Not Running'}")
        if appium_ok:
            st.success("Appium is reachable")
        else:
            st.error("Start Appium (e.g. `appium`)")

        ios_ok = check_ios_simulator_connected()
        st.markdown(f"**iOS Simulator:** {'Connected' if ios_ok else 'Not Connected'}")
        if ios_ok:
            st.success("Simulator is booted")
        else:
            st.warning("Open Simulator (e.g. `open -a Simulator`)")

        android_ok = check_android_emulator_connected()
        st.markdown(f"**Android Emulator:** {'Connected' if android_ok else 'Not Connected'}")
        if android_ok:
            st.success("Emulator is connected")
        else:
            st.warning("Start an Android AVD")

    st.title("AI QA Regression Testing Agent")
    st.markdown("---")

    # ----- Section 1: Bug Description -----
    st.header("Bug Description")
    bug_description = st.text_area(
        "Enter the bug description",
        placeholder="e.g. WiFi screen crashes when opened",
        height=120,
        key="bug_description",
    )

    # ----- Section 2: Generate Test Steps (structured JSON) -----
    # Do not assign to st.session_state["bug_description"] — the widget with key="bug_description" owns it.
    st.header("Generate Test Steps")
    if st.button("Generate Test Steps"):
        if not (bug_description or "").strip():
            st.warning("Enter a bug description first.")
        else:
            try:
                from ai_engine.test_step_generator import generate_executable_steps
                steps = generate_executable_steps(bug_description.strip())
                st.session_state["generated_steps"] = steps
                st.session_state["last_bug_description"] = bug_description.strip()
            except Exception as e:
                st.error(f"Failed to generate steps: {e}")
                st.session_state["generated_steps"] = None

    if st.session_state.get("generated_steps") is not None:
        steps = st.session_state["generated_steps"]
        st.subheader("Generated steps (executable JSON)")
        st.json(steps)

    st.markdown("---")

    # ----- Section 3: Automation Testing -----
    st.header("Automation Testing")
    col_ios, col_android = st.columns(2)
    run_ios = col_ios.button("Run iOS Regression Test", key="run_ios")
    run_android = col_android.button("Run Android Regression Test", key="run_android")

    structured_steps = st.session_state.get("generated_steps")
    bug_desc = st.session_state.get("last_bug_description", "")

    # Run iOS: use executor if structured steps exist, else legacy ios_test.py
    if run_ios:
        if structured_steps:
            try:
                from automation.executor import run_structured_test
                from reports.history import save_run_report
                with st.spinner("Running test…"):
                    result = run_structured_test("iOS", structured_steps, bug_desc)
                save_run_report(result)
                st.session_state["ios_result"] = result
            except Exception as e:
                st.session_state["ios_result"] = {"status": "FAIL", "error": str(e), "screenshot": None, "video": None}
        else:
            # Legacy: run ios_test.py
            ios_script = PROJECT_ROOT / "ios_test.py"
            if not ios_script.exists():
                st.error(f"Script not found: {ios_script}")
            else:
                with st.spinner("Running test…"):
                    proc = subprocess.run(
                        [sys.executable, str(ios_script)],
                        cwd=str(PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                passed = proc.returncode == 0 and "PASS" in (proc.stdout or "")
                from datetime import datetime
                from reports.history import save_run_report
                save_run_report({
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "platform": "iOS",
                    "bug_description": bug_desc,
                    "status": "PASS" if passed else "FAIL",
                    "screenshot": str(REPORTS_SCREENSHOTS / "ios_wifi_settings.png") if (REPORTS_SCREENSHOTS / "ios_wifi_settings.png").exists() else None,
                    "video": None,
                })
                st.session_state["ios_result"] = {
                    "status": "PASS" if passed else "FAIL",
                    "error": (proc.stderr or "").strip() or None,
                    "screenshot": str(REPORTS_SCREENSHOTS / "ios_wifi_settings.png") if (REPORTS_SCREENSHOTS / "ios_wifi_settings.png").exists() else str(REPORTS_SCREENSHOTS / "ios_wifi_error.png") if (REPORTS_SCREENSHOTS / "ios_wifi_error.png").exists() else None,
                    "video": None,
                }

    # Run Android: use executor if structured steps exist, else legacy android_test
    if run_android:
        if structured_steps:
            try:
                from automation.executor import run_structured_test
                from reports.history import save_run_report
                with st.spinner("Running test…"):
                    result = run_structured_test("Android", structured_steps, bug_desc)
                save_run_report(result)
                st.session_state["android_result"] = result
            except Exception as e:
                st.session_state["android_result"] = {"status": "FAIL", "error": str(e), "screenshot": None, "video": None}
        else:
            with st.spinner("Running test…"):
                proc = subprocess.run(
                    [sys.executable, "-m", "automation.android_test"],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            passed = proc.returncode == 0 and "PASS" in (proc.stdout or "")
            from datetime import datetime
            from reports.history import save_run_report
            save_run_report({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "platform": "Android",
                "bug_description": bug_desc,
                "status": "PASS" if passed else "FAIL",
                "screenshot": str(REPORTS_SCREENSHOTS / "android_wifi_settings.png") if (REPORTS_SCREENSHOTS / "android_wifi_settings.png").exists() else None,
                "video": None,
            })
            st.session_state["android_result"] = {
                "status": "PASS" if passed else "FAIL",
                "error": (proc.stderr or "").strip() or None,
                "screenshot": str(REPORTS_SCREENSHOTS / "android_wifi_settings.png") if (REPORTS_SCREENSHOTS / "android_wifi_settings.png").exists() else str(REPORTS_SCREENSHOTS / "android_wifi_error.png") if (REPORTS_SCREENSHOTS / "android_wifi_error.png").exists() else None,
                "video": None,
            }

    st.markdown("---")

    # ----- Section 4: Results & Evidence -----
    st.header("Results & Evidence")

    def show_result(platform: str, result: dict):
        if not result:
            return
        status = result.get("status", "FAIL")
        color = "green" if status == "PASS" else "red"
        st.markdown(
            f"**Result:** <span style='color:{color}; font-weight:bold; font-size:1.2em'>{status}</span>",
            unsafe_allow_html=True,
        )
        if result.get("error"):
            st.code(result["error"], language="text")
        screenshot = result.get("screenshot")
        if screenshot and Path(screenshot).exists():
            st.caption("Screenshot")
            st.image(screenshot, use_container_width=True)
        else:
            st.caption("Screenshot: not available")
        video = result.get("video")
        if video and Path(video).exists():
            st.caption("Recording")
            st.video(video)
        else:
            st.caption("No recording for this run.")

    if st.session_state.get("ios_result"):
        st.subheader("iOS Test")
        show_result("iOS", st.session_state["ios_result"])
    if st.session_state.get("android_result"):
        st.subheader("Android Test")
        show_result("Android", st.session_state["android_result"])
    if not st.session_state.get("ios_result") and not st.session_state.get("android_result"):
        st.info("Run an iOS or Android test to see results and evidence here.")

    st.markdown("---")

    # ----- Section 5: Test History (last 5) -----
    st.header("Test History (last 5 runs)")
    try:
        from reports.history import get_last_reports
        history = get_last_reports(5)
        if history:
            for r in history:
                platform = r.get("platform", "?")
                status = r.get("status", "?")
                ts = r.get("timestamp", "")[:19]
                st.markdown(f"**{ts}** | {platform} | **{status}**")
        else:
            st.caption("No test history yet.")
    except Exception:
        st.caption("No test history yet.")


if __name__ == "__main__":
    main()
