"""
Streamlit dashboard for the AI QA Regression Testing Agent.
Provides: bug input, AI test-step generation, Run iOS/Android regression, PASS/FAIL and evidence.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from ai_engine.test_step_generator import generate_test_plan
from automation.test_runner import run_ios_regression_test, run_android_regression_test
from reports.regression_report import save_regression_report
from config.settings import ensure_dirs


def main() -> None:
    ensure_dirs()
    st.set_page_config(
        page_title="AI QA Regression Testing Agent",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("AI QA Regression Testing Agent")
    st.caption(
        "Enter a bug description → generate test steps (AI) → run regression on iOS/Android → view PASS/FAIL and evidence."
    )

    # Bug description input
    st.header("1. Bug description")
    bug_description = st.text_area(
        "Bug description",
        placeholder="e.g. WiFi screen crashes when opened",
        height=120,
        key="bug_description",
    )

    # Generate test steps
    st.header("2. Generate test steps")
    if st.button("Generate Test Steps"):
        if not bug_description.strip():
            st.warning("Enter a bug description first.")
        else:
            with st.spinner("Generating test steps…"):
                plan = generate_test_plan(
                    bug_description=bug_description.strip(),
                    test_name="regression_test",
                )
            st.session_state["test_plan"] = plan

    if st.session_state.get("test_plan"):
        plan = st.session_state["test_plan"]
        st.subheader("Generated steps")
        for step in plan.steps:
            st.markdown(f"**{step.step_number}.** {step.description}")
        st.session_state["test_name"] = plan.test_name

    st.divider()
    st.header("3. Run regression tests")

    col_ios, col_android = st.columns(2)
    test_name = st.session_state.get("test_name", "regression_test")

    with col_ios:
        if st.button("Run iOS Regression Test", key="run_ios"):
            with st.spinner("Running iOS test (Settings → Wi‑Fi)…"):
                result = run_ios_regression_test(test_name=test_name)
            save_regression_report(result)
            st.session_state["last_ios_result"] = result

    with col_android:
        if st.button("Run Android Regression Test", key="run_android"):
            with st.spinner("Running Android test (Settings → Wi‑Fi)…"):
                result = run_android_regression_test(test_name=test_name)
            save_regression_report(result)
            st.session_state["last_android_result"] = result

    st.divider()
    st.header("4. Results & evidence")

    for platform_label, key in [("iOS", "last_ios_result"), ("Android", "last_android_result")]:
        result = st.session_state.get(key)
        if not result:
            continue
        with st.container(border=True):
            st.subheader(platform_label)
            status = result.get("status", "FAIL")
            color = "green" if status == "PASS" else "red"
            st.markdown(
                f"**Result:** <span style='color:{color}; font-weight:bold; font-size:1.1em'>{status}</span>",
                unsafe_allow_html=True,
            )
            if result.get("error"):
                st.code(result["error"], language="text")
            c1, c2 = st.columns(2)
            with c1:
                screenshot = result.get("screenshot")
                if screenshot and Path(screenshot).exists():
                    st.caption("Screenshot")
                    st.image(screenshot, use_container_width=True)
                else:
                    st.caption("Screenshot: not available")
            with c2:
                video = result.get("video")
                if video and Path(video).exists():
                    st.caption("Recording")
                    st.video(video)
                else:
                    st.caption("Recording: not available")


if __name__ == "__main__":
    main()
