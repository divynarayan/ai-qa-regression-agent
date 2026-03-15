"""
AI QA Regression Testing Agent — Streamlit dashboard.
Bug description → Generate test steps → Run iOS/Android regression → PASS/FAIL + evidence.
"""

import subprocess
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_SCREENSHOTS = PROJECT_ROOT / "reports" / "screenshots"
REPORTS_RECORDINGS = PROJECT_ROOT / "reports" / "recordings"
APPIUM_URL = "http://127.0.0.1:4723"


def check_appium_running() -> bool:
    """Return True if Appium server responds at APPIUM_URL."""
    try:
        import urllib.request
        req = urllib.request.urlopen(f"{APPIUM_URL}/status", timeout=2)
        return req.status == 200
    except Exception:
        return False


def check_ios_simulator_connected() -> bool:
    """Return True if at least one iOS simulator is booted."""
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


def main() -> None:
    st.set_page_config(
        page_title="AI QA Regression Testing Agent",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ----- Sidebar: System Status -----
    with st.sidebar:
        st.header("System Status")
        appium_ok = check_appium_running()
        st.markdown(
            f"**Appium Server:** {'Running' if appium_ok else 'Not Running'}"
        )
        if appium_ok:
            st.success("Appium is reachable")
        else:
            st.error("Start Appium (e.g. `appium`)")

        ios_ok = check_ios_simulator_connected()
        st.markdown(
            f"**iOS Simulator:** {'Connected' if ios_ok else 'Not Connected'}"
        )
        if ios_ok:
            st.success("Simulator is booted")
        else:
            st.warning("Open Simulator (e.g. `open -a Simulator`)")

    # ----- Page title -----
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

    # ----- Section 2: Generate Test Steps -----
    st.header("Generate Test Steps")
    if st.button("Generate Test Steps"):
        if not (bug_description or "").strip():
            st.warning("Enter a bug description first.")
        else:
            try:
                from ai_engine.test_step_generator import generate_test_steps
                steps = generate_test_steps(bug_description.strip())
                st.session_state["generated_steps"] = steps
            except Exception as e:
                st.error(f"Failed to generate steps: {e}")
                st.session_state["generated_steps"] = None

    if st.session_state.get("generated_steps"):
        st.subheader("Generated steps")
        for step in st.session_state["generated_steps"]:
            num = step.get("step_number", "")
            desc = step.get("description", "")
            st.markdown(f"**{num}.** {desc}")

    st.markdown("---")

    # ----- Section 3: Automation Testing -----
    st.header("Automation Testing")

    col_ios, col_android = st.columns(2)
    with col_ios:
        run_ios = st.button("Run iOS Regression Test", key="run_ios")
    with col_android:
        run_android = st.button("Run Android Regression Test", key="run_android")

    ios_script = PROJECT_ROOT / "ios_test.py"
    android_script = PROJECT_ROOT / "automation" / "android_test.py"

    if run_ios:
        if not ios_script.exists():
            st.error(f"Script not found: {ios_script}")
        else:
            with st.spinner("Running iOS regression test…"):
                proc = subprocess.run(
                    [sys.executable, str(ios_script)],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            out = (proc.stdout or "").strip()
            passed = proc.returncode == 0 and "PASS" in out
            st.session_state["ios_result"] = "PASS" if passed else "FAIL"
            st.session_state["ios_stderr"] = (proc.stderr or "").strip()

    if run_android:
        if not android_script.exists():
            st.error(f"Script not found: {android_script}")
        else:
            with st.spinner("Running Android regression test…"):
                proc = subprocess.run(
                    [sys.executable, "-m", "automation.android_test"],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            out = (proc.stdout or "").strip()
            passed = proc.returncode == 0 and "PASS" in out
            st.session_state["android_result"] = "PASS" if passed else "FAIL"
            st.session_state["android_stderr"] = (proc.stderr or "").strip()

    st.markdown("---")

    # ----- Section 4: Results & Evidence -----
    st.header("Results & Evidence")

    # iOS result
    if st.session_state.get("ios_result"):
        st.subheader("iOS Regression Test")
        result = st.session_state["ios_result"]
        color = "green" if result == "PASS" else "red"
        st.markdown(
            f"**Result:** <span style='color:{color}; font-weight:bold; font-size:1.2em'>{result}</span>",
            unsafe_allow_html=True,
        )
        if st.session_state.get("ios_stderr"):
            st.code(st.session_state["ios_stderr"], language="text")
        REPORTS_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        img = REPORTS_SCREENSHOTS / "ios_wifi_settings.png"
        err_img = REPORTS_SCREENSHOTS / "ios_wifi_error.png"
        if img.exists():
            st.caption("Screenshot")
            st.image(str(img), use_container_width=True)
        elif err_img.exists():
            st.caption("Screenshot (error)")
            st.image(str(err_img), use_container_width=True)
        else:
            st.caption("No screenshot for this run.")
        REPORTS_RECORDINGS.mkdir(parents=True, exist_ok=True)
        videos = list(REPORTS_RECORDINGS.glob("*.mp4"))
        if videos:
            latest = max(videos, key=lambda p: p.stat().st_mtime)
            st.caption("Recording")
            st.video(str(latest))
        else:
            st.caption("No recording available.")

    # Android result
    if st.session_state.get("android_result"):
        st.subheader("Android Regression Test")
        result = st.session_state["android_result"]
        color = "green" if result == "PASS" else "red"
        st.markdown(
            f"**Result:** <span style='color:{color}; font-weight:bold; font-size:1.2em'>{result}</span>",
            unsafe_allow_html=True,
        )
        if st.session_state.get("android_stderr"):
            st.code(st.session_state["android_stderr"], language="text")
        REPORTS_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        img = REPORTS_SCREENSHOTS / "android_wifi_settings.png"
        err_img = REPORTS_SCREENSHOTS / "android_wifi_error.png"
        if img.exists():
            st.caption("Screenshot")
            st.image(str(img), use_container_width=True)
        elif err_img.exists():
            st.caption("Screenshot (error)")
            st.image(str(err_img), use_container_width=True)
        else:
            st.caption("No screenshot for this run.")
        REPORTS_RECORDINGS.mkdir(parents=True, exist_ok=True)
        videos = list(REPORTS_RECORDINGS.glob("*.mp4"))
        if videos:
            latest = max(videos, key=lambda p: p.stat().st_mtime)
            st.caption("Recording")
            st.video(str(latest))
        else:
            st.caption("No recording available.")

    if not st.session_state.get("ios_result") and not st.session_state.get("android_result"):
        st.info("Run an iOS or Android regression test to see results and evidence here.")


if __name__ == "__main__":
    main()
