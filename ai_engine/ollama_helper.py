import re

import requests
import yaml

OLLAMA_URL = "http://localhost:11434/api/generate"


_SAFE_FALLBACK_YAML = """\
steps:
  - action: tap
    target: "Entrar a mi cuenta"
  - action: input
    field: "Teléfono"
    value: "{{phone_number}}"
  - action: input
    field: "Contraseña"
    value: "{{password}}"
  - action: tap
    target: "Entrar"
  - action: verify_element
    target: "Inicio"
"""


def _sanitize_ollama_yaml(raw: str) -> str:
    """Strip prose/markdown and keep the YAML block tinyllama sometimes wraps."""
    if not raw or not str(raw).strip():
        return ""
    s = str(raw).strip()
    # Fenced code block
    m = re.search(r"```(?:yaml|yml)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        s = m.group(1).strip()
    # Start from steps: if model added chatter before it
    idx = s.lower().find("steps:")
    if idx != -1:
        s = s[idx:].strip()
    return s


def _repair_common_yaml_issues(text: str) -> str:
    """
    Fix frequent tinyllama mistakes that break PyYAML (e.g. 'Target:' instead of 'target:').
    """
    if not text:
        return text
    # Wrong key casing / prose-style keys
    text = re.sub(r"(?m)^(\s*)Target:\s*", r"\1target: ", text)
    text = re.sub(r"(?m)^(\s*)Action:\s*", r"\1action: ", text)
    text = re.sub(r"(?m)^(\s*)Field:\s*", r"\1field: ", text)
    text = re.sub(r"(?m)^(\s*)Value:\s*", r"\1value: ", text)
    return text


def _parse_yaml_steps(raw: str):
    """Return parsed dict or None."""
    s = _sanitize_ollama_yaml(raw)
    s = _repair_common_yaml_issues(s)
    if not s:
        return None, s
    try:
        parsed = yaml.safe_load(s)
        if isinstance(parsed, dict) and "steps" in parsed:
            return parsed, s
    except Exception:
        pass
    return None, s


def generate_yaml_from_ai(bug_description, manual_steps, pdf_text=None):
    prompt = f"""
You are a mobile QA automation expert.

Convert manual QA steps into STRICT YAML format.

IMPORTANT RULES:
- Use EXACT UI text from steps or PDF (Spanish UI when the app is Spanish)
- Do NOT translate text (keep Spanish if present)
- Example UI labels: "Teléfono", "Contraseña", "Entrar a mi cuenta"
- Use these exact labels when applicable:
  - "Entrar a mi cuenta" (login from landing)
  - "Registrarme" (registration from landing)
  - "Más" (app icon on home, only if steps say so)
  - "Teléfono"
  - "Contraseña"
  - "Entrar"
  - "Inicio" (after login)
- STRICT: NEVER use English UI strings: Login, Password, Phone, Submit, Home, Sign in, Log in
- REQUIRED Spanish labels for this app: "Entrar a mi cuenta", "Registrarme", "Teléfono", "Contraseña", "Entrar", "Inicio"
- For post-login verification use "Inicio" (not "Home")
- Output MUST be valid YAML
- DO NOT return numbered list
- DO NOT return explanation
- ONLY return YAML
- YAML keys MUST be lowercase: target, action, field, value (NEVER use `Target:` or `Action:`)

FORMAT:

steps:
  - action: tap
    target: "Entrar a mi cuenta"
  - action: input
    field: "Teléfono"
    value: "{{phone_number}}"
  - action: input
    field: "Contraseña"
    value: "{{password}}"
  - action: tap
    target: "Entrar"
  - action: verify_element
    target: "Inicio"

RULES:
- Use ONLY: tap, input, verify_element
- Always include "steps:" root key
- Use quotes around all text
- Use {{phone_number}} and {{password}}
- No WiFi or Settings
- If element not visible, assume scrolling
- Always use real UI labels
- Example mapping:
  - Login → "Entrar a mi cuenta"
  - Phone → "Teléfono"
  - Password → "Contraseña"
  - Home / success → use real Spanish label from PDF (e.g. "Inicio"), never "Home"

Bug:
{bug_description}

Steps:
{manual_steps}
"""
    if pdf_text:
        prompt += f"\n\nUI CONTEXT FROM FIGMA/PDF:\n{pdf_text}\n"

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "tinyllama",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    # Enough tokens for full steps: block (truncated YAML causes parse errors).
                    "num_predict": 512,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        raw_output = response.json().get("response", "")
        parsed, cleaned = _parse_yaml_steps(raw_output)
        if parsed is not None:
            # Return normalized YAML string so downstream yaml.safe_load is stable.
            return yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)
        raise ValueError("Invalid YAML format after sanitize/repair")
    except Exception as e:
        # Demo-safe: never block the run on bad LLM output.
        print("Ollama YAML unusable, using safe fallback:", e)
        return _SAFE_FALLBACK_YAML


def chat_with_ai(message):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "tinyllama",
                "prompt": message,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 200,
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print("Ollama failed (chat):", e)
        return "AI is currently unavailable. Please run using the existing YAML or Fast Mode."

