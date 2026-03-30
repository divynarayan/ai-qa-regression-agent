import json
import yaml
import subprocess
import sys
from pathlib import Path
import streamlit as st
import io

from ai_engine.ollama_helper import generate_yaml_from_ai, chat_with_ai
from ai_engine.pdf_parser import extract_text_from_pdf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPIUM_URL = "http://127.0.0.1:4723"


# ---------------- SYSTEM CHECKS ---------------- #

def check_appium_running():
    try:
        import urllib.request
        res = urllib.request.urlopen(f"{APPIUM_URL}/status", timeout=2)
        return res.status == 200
    except:
        return False


def check_ios():
    try:
        proc = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "booted"],
            capture_output=True, text=True
        )
        return "Booted" in proc.stdout
    except:
        return False


def check_android():
    try:
        proc = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        return "device" in proc.stdout
    except:
        return False


# ---------------- MAIN APP ---------------- #

def main():
    st.set_page_config(page_title="AI QA Agent", layout="wide")

    # Sidebar
    with st.sidebar:
        st.header("System Status")

        if check_appium_running():
            st.success("Appium Running")
        else:
            st.error("Start Appium")

        if check_ios():
            st.success("iOS Connected")
        else:
            st.warning("Start iOS Simulator")

        if check_android():
            st.success("Android Connected")
        else:
            st.warning("Start Android Emulator")

    st.title("AI QA Regression Testing Agent")
    st.markdown("---")

    # ---------------- BUG ---------------- #
    st.header("Bug Description")
    bug_description = st.text_area("Enter bug")

    # ---------------- MANUAL STEPS ---------------- #
    st.header("Manual Steps")
    manual_steps = st.text_area("Enter steps")

    # ---------------- FIGMA ---------------- #
    figma = st.file_uploader("Upload Screenshot (optional)", type=["png", "jpg"])
    if figma:
        st.image(figma)

    # ---------------- FIGMA PDF (EXPORT) ---------------- #
    figma_pdf = st.file_uploader("Upload Figma Export (PDF, optional)", type=["pdf"])
    pdf_text = None
    if figma_pdf:
        try:
            pdf_bytes = figma_pdf.getvalue()
            pdf_text = extract_text_from_pdf(io.BytesIO(pdf_bytes))
            st.caption("Extracted PDF text (used as UI context for AI)")
            st.text_area("PDF Text", value=pdf_text[:5000], height=160)
        except Exception as e:
            st.warning(f"Could not parse PDF: {e}")

    # ---------------- AI YAML GENERATION (OLLAMA) ---------------- #
    st.header("AI YAML Generation (Ollama)")

    fast_mode = st.checkbox("⚡ Fast Mode (Skip AI) - use default YAML")

    if st.button("🚀 Generate YAML with AI"):
        if fast_mode:
            from ai_engine.ollama_helper import _SAFE_FALLBACK_YAML  # type: ignore[attr-defined]
            yaml_output = _SAFE_FALLBACK_YAML
        else:
            if not (bug_description or "").strip() or not (manual_steps or "").strip():
                st.warning("Please enter bug description and manual steps")
                yaml_output = None
            else:
                with st.spinner("AI generating..."):
                    yaml_output = generate_yaml_from_ai(bug_description, manual_steps, pdf_text=pdf_text)

        if yaml_output:
            st.session_state["generated_yaml"] = yaml_output

            # Extract steps immediately for execution.
            parsed = yaml.safe_load(yaml_output) or {}
            if isinstance(parsed, dict):
                st.session_state["generated_steps"] = parsed.get("steps", [])

    # Always display the latest generated YAML + extracted steps (if present)
    if st.session_state.get("generated_yaml"):
        st.subheader("Generated YAML")
        st.code(st.session_state["generated_yaml"], language="yaml")

        # Demo-stability warning: English labels usually mean wrong UI text.
        english_markers = ["\"Login\"", "\"Password\"", "\"Phone\"", "target: \"Login\"", "field: \"Password\"", "field: \"Phone\""]
        if any(m in st.session_state["generated_yaml"] for m in english_markers):
            st.warning(
                "YAML contains English labels (Login/Phone/Password). For Spanish UI, update to your real labels like "
                "\"Entrar a mi cuenta\", \"Teléfono\", \"Contraseña\" to avoid element-not-found during the demo."
            )

        if "generated_steps" in st.session_state:
            st.caption("Extracted steps")
            st.json(st.session_state["generated_steps"])

    st.markdown("---")

    # ---------------- JSON INPUT (MANUAL) ---------------- #
    st.header("JSON Test Data (Manual)")
    json_text = st.text_area(
        "Paste JSON test data (manual input)",
        value=st.session_state.get("json_test_data", '{\n  "phone_number": "66728317",\n  "password": "Test@1010"\n}'),
        height=140,
        key="json_test_data",
    )
    try:
        test_data = json.loads(json_text) if json_text else {}
        if not isinstance(test_data, dict):
            raise ValueError("JSON must be an object")
        st.caption("Parsed JSON")
        st.json(test_data)
        st.session_state["parsed_test_data"] = test_data
    except Exception as e:
        st.warning(f"Invalid JSON: {e}")
        st.session_state["parsed_test_data"] = {}

    # ---------------- RUN ---------------- #
    st.header("Automation Testing")

    col1, col2 = st.columns(2)

    if col1.button("Run iOS Test"):
        run_test("iOS")

    if col2.button("Run Android Test"):
        run_test("Android")

    # ---------------- RESULT ---------------- #
    st.header("Result")

    if "result" in st.session_state:
        res = st.session_state["result"]

        if res["status"] == "PASS":
            st.success("PASS")
        else:
            st.error("FAIL")

        if res.get("error"):
            st.code(res["error"])

        if res.get("screenshot"):
            st.image(res["screenshot"])

    st.markdown("---")

    # ---------------- AI QA CHATBOT (OLLAMA) ---------------- #
    st.header("🤖 AI QA Chatbot")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_input = st.chat_input("Ask AI to test something...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("Ollama thinking..."):
            ai_response = chat_with_ai(user_input)
        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])


# ---------------- EXECUTION ---------------- #

def run_test(platform):
    # Prefer AI-generated steps; fallback to legacy "steps" if present.
    steps = st.session_state.get("generated_steps") or st.session_state.get("steps")

    if not steps:
        st.warning("Generate steps first")
        return

    try:
        from automation.executor import run_structured_test, run_test_case

        with st.spinner(f"Running {platform} test..."):
            # If we have full YAML + JSON, run via run_test_case for variable substitution.
            if st.session_state.get("generated_yaml"):
                test_case = yaml.safe_load(st.session_state["generated_yaml"]) or {}
                test_data = st.session_state.get("parsed_test_data") or {}
                result = run_test_case(test_case, test_data, platform=platform)
            else:
                bug_desc = st.session_state.get("bug_description") or ""
                result = run_structured_test(platform, steps, bug_desc)

        st.session_state["result"] = result

    except Exception as e:
        st.session_state["result"] = {
            "status": "FAIL",
            "error": str(e)
        }


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    main()


# ---------------- COMPATIBILITY WRAPPERS ---------------- #
# Keep `app.py` imports working if internal check names differ.

def check_android_emulator_connected():
    return check_android()


def check_ios_simulator_connected():
    return check_ios()