"""
Autonomous Chat-Driven AI QA Regression Agent entrypoint.

Run from repo root:
    streamlit run app.py

Two modes:
- Manual Mode: existing dashboard (YAML/JSON upload, status checks, regression buttons)
- AI Agent Mode: chat-driven BUG flow → generate YAML/JSON → run automation → evidence
"""

from __future__ import annotations

import json
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import yaml

from automation.executor import run_test_case
from ui.dashboard import (  # type: ignore[attr-defined]
    check_android_emulator_connected,
    check_appium_running,
    check_ios_simulator_connected,
)


BUG_ID_REGEX = re.compile(r"\b(BUG|APP|AC)-\d+\b", re.IGNORECASE)


def _ensure_session_defaults() -> None:
    st.session_state.setdefault("chat_messages", [])
    st.session_state.setdefault("agent_yaml", "")
    st.session_state.setdefault("agent_json", {})
    st.session_state.setdefault("agent_bug_id", "")
    st.session_state.setdefault("agent_results", [])
    st.session_state.setdefault("bug_description", "")
    st.session_state.setdefault("manual_steps", "")
    st.session_state.setdefault("manual_json_data", "{}")
    st.session_state.setdefault("agent_bdd", "")
    st.session_state.setdefault("agent_step_expectations", [])
    st.session_state.setdefault("agent_notes", "")
    st.session_state.setdefault("agent_ui_mismatches", [])


def _extract_or_generate_bug_id(text: str) -> str:
    m = BUG_ID_REGEX.search(text or "")
    if m:
        return m.group(0).upper()
    return f"BUG-{random.randint(10000, 99999)}"


def _parse_manual_steps(text: str) -> List[str]:
    lines = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        # remove list prefixes like "1.", "-", "*"
        s = re.sub(r"^\s*(\d+[\).\]]\s*|[-*]\s*)", "", s).strip()
        if s:
            lines.append(s)
    return lines


def _infer_step_action(step: str) -> Tuple[str, Dict[str, Any]]:
    """
    Heuristic mapping from a natural-language manual step to an executor-compatible action.
    This is intentionally conservative; when ambiguous, we return "UNKNOWN".
    """
    s = (step or "").strip()
    low = s.lower()

    # Launch/open
    if any(k in low for k in ["open app", "launch app", "start app", "abrir", "iniciar", "launch the app"]):
        return "open_app", {}

    # Tap/click
    m = re.search(r"\"([^\"]+)\"", s)
    quoted = m.group(1).strip() if m else None
    if any(k in low for k in ["tap", "click", "press", "select", "tocar", "pulsar"]):
        if quoted:
            return "tap", {"target": quoted}
        # fallback: try after keyword
        after = re.split(r"\btap\b|\bclick\b|\bpress\b|\bselect\b|\btocar\b|\bpulsar\b", s, maxsplit=1, flags=re.IGNORECASE)
        target = after[1].strip() if len(after) > 1 else ""
        target = target.strip(": ").strip()
        return ("tap", {"target": target}) if target else ("UNKNOWN", {"raw": s})

    # Input/type/enter
    if any(k in low for k in ["enter", "type", "input", "fill", "set", "ingresar", "escribir"]):
        field = None
        value_key = None
        if quoted:
            # Often field is quoted.
            field = quoted
        # Try "into <field>"
        m2 = re.search(r"\binto\s+(.+)$", s, re.IGNORECASE)
        if m2 and not field:
            field = m2.group(1).strip()
        # Create template variable from field
        if field:
            norm = re.sub(r"[^a-zA-Z0-9_]+", "_", field).strip("_").lower()
            value_key = norm or "value"
        return ("input", {"field": field or "", "value": f"{{{{{value_key}}}}}"}) if field else ("UNKNOWN", {"raw": s})

    # Verify/assert/expect/see
    if any(k in low for k in ["verify", "assert", "expect", "should see", "see ", "validate", "debe", "verificar"]):
        if quoted:
            return "verify_element", {"target": quoted}
        # Try after keyword
        after = re.split(r"\bverify\b|\bassert\b|\bexpect\b|\bshould see\b|\bvalidate\b|\bverificar\b", s, maxsplit=1, flags=re.IGNORECASE)
        target = after[1].strip() if len(after) > 1 else ""
        target = target.strip(": ").strip()
        return ("verify_element", {"target": target}) if target else ("UNKNOWN", {"raw": s})

    # Scroll
    if any(k in low for k in ["scroll", "swipe", "desplazar", "deslizar"]):
        return "scroll", {}

    return "UNKNOWN", {"raw": s}


def _build_bdd(bug_id: str, bug_description: str, manual_steps: List[str]) -> str:
    title = bug_description.strip() or f"Regression validation for {bug_id}"
    lines = [f"Scenario: {title}", "", "Given the user launches the mobile application"]
    for s in manual_steps:
        action, meta = _infer_step_action(s)
        if action == "tap":
            lines.append(f'When the user taps the "{meta.get("target")}" button')
        elif action == "input":
            lines.append(f'And the user enters a value into "{meta.get("field")}"')
        elif action == "verify_element":
            lines.append(f'Then the user should see "{meta.get("target")}"')
        elif action == "scroll":
            lines.append("And the user scrolls to find the next element")
        elif action == "open_app":
            # already covered by Given
            pass
        else:
            lines.append(f"And {s}")
    return "\n".join(lines).strip() + "\n"


def _generate_yaml_from_manual(
    bug_id: str,
    bug_description: str,
    manual_steps_text: str,
    manual_json_data: Optional[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any], List[Dict[str, str]], str, List[str]]:
    """
    Dynamic YAML generation driven by QA-provided manual steps (primary source of truth).
    Produces:
    - yaml_output (elements + steps)
    - json_template (template only; values blank)
    - step_expectations: list of {"step": ..., "expected": ...}
    - notes
    - mismatches (if any UI mismatch detected; currently conservative)
    """
    manual_steps = _parse_manual_steps(manual_steps_text)
    if not manual_steps:
        raise ValueError("Manual Test Steps are required in AI Agent Mode.")

    # Build elements + steps conservatively from manual steps.
    elements: Dict[str, Any] = {}
    steps: List[Dict[str, Any]] = [{"action": "open_app"}, {"action": "start_recording"}]

    json_template: Dict[str, Any] = {}
    expectations: List[Dict[str, str]] = []
    notes: List[str] = []
    mismatches: List[str] = []

    for s in manual_steps:
        action, meta = _infer_step_action(s)
        if action == "UNKNOWN":
            # Safety rule: don't guess.
            raise ValueError(
                f'Unable to confidently convert this manual step into automation: "{s}". '
                "Please rephrase it using action verbs like tap/input/verify/scroll and include quoted labels, "
                'e.g. Tap "Login", Input "Password", Verify "Home".'
            )

        if action == "tap":
            label = (meta.get("target") or "").strip()
            if not label:
                raise ValueError(f'Please specify what to tap in step: "{s}" (e.g. Tap "Login").')
            key = re.sub(r"[^a-zA-Z0-9_]+", "_", label).strip("_").lower() + "_button"
            elements.setdefault(
                key,
                {"type": "button", "locator": "accessibility_id", "value": label},
            )
            steps.append({"action": "tap", "target": key})
            expectations.append({"step": s, "expected": f'The app registers a tap on "{label}".'})

        elif action == "input":
            field = (meta.get("field") or "").strip()
            value = (meta.get("value") or "").strip()
            if not field:
                raise ValueError(f'Please specify which field to input in step: "{s}" (e.g. Input "Password").')
            field_key = re.sub(r"[^a-zA-Z0-9_]+", "_", field).strip("_").lower() + "_field"
            elements.setdefault(
                field_key,
                {"type": "input", "locator": "accessibility_id", "value": field},
            )
            # template variable
            m = re.search(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", value)
            var = m.group(1) if m else re.sub(r"[^a-zA-Z0-9_]+", "_", field).strip("_").lower()
            json_template.setdefault(var, "")
            steps.append({"action": "input", "target": field_key, "value": f"{{{{{var}}}}}"})
            expectations.append({"step": s, "expected": f'The field "{field}" is populated.'})

        elif action == "verify_element":
            target = (meta.get("target") or "").strip()
            if not target:
                raise ValueError(f'Please specify what to verify in step: "{s}" (e.g. Verify "Home").')
            steps.append({"action": "verify_element", "target": target})
            expectations.append({"step": s, "expected": f'The UI shows "{target}".'})

        elif action == "scroll":
            steps.append({"action": "scroll"})
            expectations.append({"step": s, "expected": "More UI content becomes visible."})

        elif action == "open_app":
            # Keep only the initial open_app
            expectations.append({"step": s, "expected": "The application launches successfully."})

    steps.append({"action": "capture_screenshot"})
    steps.append({"action": "stop_recording"})

    # Merge any manually supplied JSON keys into the template (template-only policy).
    if isinstance(manual_json_data, dict):
        for k in manual_json_data.keys():
            json_template.setdefault(str(k), "")

    # Notes / edge cases
    notes.append("Dynamic waits: the executor uses WebDriverWait for element lookup (no fixed sleeps).")
    notes.append('System alerts: executor attempts to auto-dismiss common "Allow/OK/Continue" prompts.')
    notes.append("Template-only JSON policy: values are intentionally blank; fill them before execution if needed.")

    module = "regression"
    screen = "UnknownScreen"
    if any("login" in (bug_description or "").lower() or "login" in s.lower() for s in manual_steps):
        module, screen = "login", "LoginScreen"
    if any("register" in (bug_description or "").lower() or "registr" in s.lower() for s in manual_steps):
        module = "registration"
        screen = "RegistrationScreen"

    yaml_obj: Dict[str, Any] = {
        "id": bug_id,
        "module": module,
        "screen": screen,
        "description": bug_description.strip() or bug_id,
        "elements": elements,
        "steps": steps,
    }
    yaml_out = yaml.safe_dump(yaml_obj, sort_keys=False, allow_unicode=True)
    return yaml_out, json_template, expectations, "\n".join(notes), mismatches


def _generate_yaml_and_data(bug_id: str, prompt: str) -> tuple[str, Dict[str, Any]]:
    """
    Backwards-compatible generator used by earlier AI agent flows.
    It now prefers QA engineer manual steps (session_state["manual_steps"]) when provided.
    """
    manual_steps_text = st.session_state.get("manual_steps", "") or ""
    manual_json_raw = st.session_state.get("manual_json_data", "{}") or "{}"
    manual_json_data: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(manual_json_raw)
        if isinstance(parsed, dict):
            manual_json_data = parsed
    except Exception:
        manual_json_data = None

    if manual_steps_text.strip():
        yaml_out, json_template, expectations, notes, mismatches = _generate_yaml_from_manual(
            bug_id=bug_id,
            bug_description=prompt,
            manual_steps_text=manual_steps_text,
            manual_json_data=manual_json_data,
        )
        st.session_state["agent_step_expectations"] = expectations
        st.session_state["agent_notes"] = notes
        st.session_state["agent_ui_mismatches"] = mismatches
        st.session_state["agent_bdd"] = _build_bdd(bug_id, prompt, _parse_manual_steps(manual_steps_text))
        return yaml_out, json_template

    # Safety: if no manual steps, do not invent flows. Ask for clarification upstream.
    raise ValueError("Manual Test Steps are required to generate automation (no static flows).")


def _render_system_status() -> None:
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


def _render_ai_agent_mode() -> None:
    _ensure_session_defaults()
    _render_system_status()

    st.title("AI QA Regression Testing Agent")
    st.markdown("---")

    # 1️⃣ Bug Description
    st.header("Bug Description")
    bug_description = st.text_area(
        "Describe the bug in natural language",
        value=st.session_state.get("bug_description", ""),
        placeholder="e.g. Run regression for BUG-404 where Registrarme button is not clickable",
        height=120,
        key="bug_description",
    )

    # 2️⃣ Chatbot Interaction
    st.header("Chatbot Interaction")
    st.caption("AI Agent Mode is driven by your manual test steps (primary source of truth).")

    st.subheader("Manual Test Steps (required)")
    st.text_area(
        "Paste the QA engineer’s manual steps (one per line). Use quoted labels for reliability, e.g. Tap \"Login\".",
        value=st.session_state.get("manual_steps", ""),
        height=140,
        key="manual_steps",
    )

    st.subheader("Optional UI Screenshot / Figma Export (secondary context)")
    ui_image = st.file_uploader("Upload UI image (png/jpg)", type=["png", "jpg", "jpeg"])
    if ui_image is not None:
        st.image(ui_image, caption="Uploaded UI image", use_container_width=True)
        st.info(
            "UI image received. If labels differ from your manual steps, please mention the exact on-screen text in quotes "
            '(e.g. Tap "Sign In" instead of "Login").'
        )

    st.subheader("Manual JSON Test Data (optional)")
    st.text_area(
        "Provide JSON keys you want available for {{variables}}. Values will be ignored in the generated template.",
        value=st.session_state.get("manual_json_data", "{}"),
        height=110,
        key="manual_json_data",
    )

    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_msg = st.chat_input("Ask QA Agent...")
    if user_msg:
        st.session_state["chat_messages"].append({"role": "user", "content": user_msg})
        bug_id = _extract_or_generate_bug_id(user_msg or bug_description)
        try:
            yaml_output, json_data = _generate_yaml_and_data(bug_id, user_msg or bug_description or bug_id)
        except Exception as e:
            assistant_text = (
                f"I couldn't generate automation yet.\n\n"
                f"Reason: {e}\n\n"
                "Please provide manual steps using clear verbs and quoted labels, for example:\n"
                '- Tap "Login"\n'
                '- Input "Password"\n'
                '- Verify "Home"\n'
            )
            st.session_state["chat_messages"].append({"role": "assistant", "content": assistant_text})
            with st.chat_message("assistant"):
                st.markdown(assistant_text)
            return

        st.session_state["agent_yaml"] = yaml_output
        st.session_state["agent_json"] = json_data
        st.session_state["agent_bug_id"] = bug_id

        # 5️⃣ Automation Testing (triggered by agent)
        responses: List[str] = []
        results: List[Dict[str, Any]] = []
        for platform in ("iOS", "Android"):
            with st.spinner(f"Running {platform} Test for {bug_id}…"):
                try:
                    test_case_obj = yaml.safe_load(yaml_output)
                    result = run_test_case(test_case_obj, json_data, bug_id=bug_id, platform=platform)
                    results.append(result)
                    status = (result.get("status") or "").upper()
                    if status == "PASS":
                        responses.append(f"{platform} regression for **{bug_id}** passed.")
                    else:
                        reason = result.get("error") or "unknown error"
                        responses.append(f"{platform} regression for **{bug_id}** failed: {reason}")
                except Exception as e:
                    responses.append(f"{platform} regression for **{bug_id}** failed: {e}")

        st.session_state["agent_results"] = results

        # Compose the required output order in the assistant response.
        bdd = st.session_state.get("agent_bdd", "")
        expectations = st.session_state.get("agent_step_expectations", []) or []
        notes = st.session_state.get("agent_notes", "")
        mismatches = st.session_state.get("agent_ui_mismatches", []) or []

        step_lines = []
        for item in expectations:
            step_lines.append(f'- **Step**: {item.get("step","")}\n  - **Expected**: {item.get("expected","")}')
        steps_md = "\n".join(step_lines) if step_lines else "_No step expectations available._"
        mismatch_md = "\n".join([f"- {m}" for m in mismatches]) if mismatches else "None detected."

        assistant_text = "\n\n".join(
            [
                "#### 1) Refined Test Case Scenario",
                f"```text\n{bdd.strip()}\n```" if bdd else "_No scenario generated._",
                "#### 2) Step-by-Step Action → Expected Result",
                steps_md,
                "#### 5) Automation Notes and Edge Cases",
                notes or "_No notes._",
                "#### Execution Results",
                "\n\n".join(responses),
                "#### UI Differences (if any)",
                mismatch_md,
            ]
        )
        st.session_state["chat_messages"].append(
            {
                "role": "assistant",
                "content": assistant_text,
            }
        )
        with st.chat_message("assistant"):
            st.markdown(assistant_text)

    st.markdown("---")

    # 3️⃣ Generated YAML
    st.header("Generated YAML")
    if st.session_state.get("agent_yaml"):
        st.code(st.session_state["agent_yaml"], language="yaml")
    else:
        st.caption("The agent will generate YAML here.")

    # 4️⃣ Generated JSON
    st.header("Generated JSON")
    if st.session_state.get("agent_json"):
        st.json(st.session_state["agent_json"])
    else:
        st.caption("The agent will generate JSON test data here.")

    st.markdown("---")

    # 5️⃣ Automation Testing (iOS + Android) – manual re-run
    st.header("Automation Testing (iOS + Android)")
    col1, col2 = st.columns(2)
    bug_id = st.session_state.get("agent_bug_id") or _extract_or_generate_bug_id(bug_description or "")
    yaml_output = st.session_state.get("agent_yaml", "")
    json_data = st.session_state.get("agent_json", {})

    if col1.button("Re-run iOS Test"):
        if not yaml_output:
            st.error("No generated YAML available yet.")
        else:
            with st.spinner(f"Running iOS Test for {bug_id}…"):
                test_case_obj = yaml.safe_load(yaml_output)
                result = run_test_case(test_case_obj, json_data, bug_id=bug_id, platform="iOS")
                st.session_state["agent_results"].append(result)
                if (result.get("status") or "").upper() == "PASS":
                    st.success("Test Passed")
                else:
                    st.error(f"Test Failed: {result.get('error') or 'unknown error'}")

    if col2.button("Re-run Android Test"):
        if not yaml_output:
            st.error("No generated YAML available yet.")
        else:
            with st.spinner(f"Running Android Test for {bug_id}…"):
                test_case_obj = yaml.safe_load(yaml_output)
                result = run_test_case(test_case_obj, json_data, bug_id=bug_id, platform="Android")
                st.session_state["agent_results"].append(result)
                if (result.get("status") or "").upper() == "PASS":
                    st.success("Test Passed")
                else:
                    st.error(f"Test Failed: {result.get('error') or 'unknown error'}")

    st.markdown("---")

    # 6️⃣ Result & Evidence
    st.header("Result & Evidence")
    last_results: List[Dict[str, Any]] = st.session_state.get("agent_results", [])  # type: ignore[assignment]

    if not last_results:
        st.caption("Run a test to see results and evidence.")
        return

    for r in last_results[-2:]:
        platform = r.get("platform", "?")
        status = (r.get("status") or "").upper()
        error_msg = r.get("error")
        screenshot_bug = r.get("screenshot_bug")
        video_bug = r.get("video_bug")

        st.subheader(f"{platform} Result")
        if status == "PASS":
            st.success("Test Passed")
        else:
            st.error("Test Failed")
            if error_msg:
                st.code(str(error_msg), language="text")

        if screenshot_bug:
            st.image(screenshot_bug)
        if video_bug:
            st.video(video_bug)


def main() -> None:
    st.set_page_config(page_title="AI QA Regression Testing Agent", layout="wide")
    _ensure_session_defaults()

    mode = st.radio(
        "Mode",
        ["AI Agent Mode", "Manual Mode"],
        horizontal=True,
        key="mode_selector",
    )

    if mode == "Manual Mode":
        # Delegate to the existing dashboard implementation so we don't break
        # YAML/JSON manual upload, regression buttons, or history.
        from ui.dashboard import main as legacy_main

        legacy_main()
    else:
        _render_ai_agent_mode()


if __name__ == "__main__":
    main()

