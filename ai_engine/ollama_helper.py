import requests
import yaml

OLLAMA_URL = "http://localhost:11434/api/generate"


_SAFE_FALLBACK_YAML = """\
steps:
  - action: tap
    target: "Login"
  - action: input
    field: "Phone"
    value: "{{phone_number}}"
  - action: input
    field: "Password"
    value: "{{password}}"
  - action: tap
    target: "Submit"
  - action: verify_element
    target: "Home"
"""


def generate_yaml_from_ai(bug_description, manual_steps):
    prompt = f"""
You are a mobile QA automation expert.

Convert manual QA steps into STRICT YAML format.

IMPORTANT RULES:
- Output MUST be valid YAML
- DO NOT return numbered list
- DO NOT return explanation
- ONLY return YAML

FORMAT:

steps:
  - action: tap
    target: "Login"
  - action: input
    field: "Phone"
    value: "{{phone_number}}"
  - action: input
    field: "Password"
    value: "{{password}}"
  - action: tap
    target: "Submit"
  - action: verify_element
    target: "Home"

RULES:
- Use ONLY: tap, input, verify_element
- Always include "steps:" root key
- Use quotes around all text
- Use {{phone_number}} and {{password}}
- No WiFi or Settings
- If element not visible, assume scrolling

Bug:
{bug_description}

Steps:
{manual_steps}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "tinyllama",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        },
        timeout=120,
    )
    response.raise_for_status()
    raw_output = response.json().get("response", "")

    try:
        parsed = yaml.safe_load(raw_output)
        if not isinstance(parsed, dict) or "steps" not in parsed:
            raise ValueError("Invalid YAML format")
        return raw_output
    except Exception:
        return _SAFE_FALLBACK_YAML


def chat_with_ai(message):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "tinyllama",
            "prompt": message,
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json().get("response", "")

