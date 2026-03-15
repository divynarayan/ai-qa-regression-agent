# AI QA Regression Testing Agent

A production-ready system that automates mobile regression testing for **iOS** and **Android** using **Appium**, with **AI-generated test steps** from bug descriptions. Evidence (screenshots, screen recordings, logs) is captured and stored for developers.

---

## Project overview

The system simulates a real QA workflow:

1. **QA uploads or writes a bug description** in the Streamlit dashboard.
2. **AI converts the bug description into test steps** (OpenAI API if configured, otherwise a built-in heuristic).
3. **Automation runs those steps** on iOS Simulator and/or Android Emulator via Appium.
4. **Evidence is captured**: screenshots and screen recording during execution.
5. **PASS/FAIL result** is shown in the dashboard.
6. **Evidence and JSON reports** are saved under `evidence/` and `reports/` for developers.

### Tech stack

- **Language:** Python  
- **UI:** Streamlit  
- **Automation:** Appium (XCUITest for iOS, UiAutomator2 for Android)  
- **AI:** OpenAI API (optional) or local heuristic  

---

## Architecture

```
Bug description
    → AI generates test steps (OpenAI or heuristic)
    → Automation runs on simulator/emulator
    → Screenshots + recording captured
    → PASS / FAIL + evidence stored
    → Dashboard shows result and evidence
```

### Folder structure

```
ai-qa-agent/
├── app.py                    # Streamlit entry point
├── dashboard/
│   └── ui.py                 # Streamlit UI (bug input, buttons, results)
├── automation/
│   ├── ios_test.py           # iOS Settings → Wi-Fi test
│   ├── android_test.py       # Android Settings → Wi-Fi test
│   └── test_runner.py        # Run iOS/Android tests
├── ai_engine/
│   ├── bug_parser.py         # TestStep / TestPlan data structures
│   └── test_step_generator.py # Bug → test steps (OpenAI or heuristic)
├── evidence/
│   ├── screenshots/          # Screenshots per run
│   ├── recordings/           # Screen recordings (MP4)
│   └── logs/                 # Log files
├── reports/                  # JSON regression reports
│   └── regression_report.py  # Save report helper
├── config/
│   └── settings.py           # Paths, Appium URL, device names
├── utils/
│   ├── recording.py          # Appium start/stop recording
│   └── screenshot.py         # Save screenshots
├── requirements.txt
└── README.md
```

---

## Setup instructions

### 1. Python environment

From the project root `ai-qa-agent/`:

```bash
cd ai-qa-agent
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Appium

- Install [Node.js](https://nodejs.org/) (LTS).
- Install Appium: `npm install -g appium`
- Install drivers:
  - `appium driver install xcuitest`
  - `appium driver install uiautomator2`
- Start Appium: `appium` (default: `http://127.0.0.1:4723`)

### 3. iOS

- Install **Xcode** and **Xcode Command Line Tools**.
- Open Simulator: `open -a Simulator` and boot a device (e.g. iPhone 16).
- Optional env: `IOS_DEVICE_NAME`, `IOS_PLATFORM_VERSION`.

### 4. Android

- Install **Android Studio** and create an **AVD** (Android Virtual Device).
- Start the emulator from Android Studio or CLI.
- Optional env: `ANDROID_DEVICE_NAME`, `ANDROID_PLATFORM_VERSION`.

### 5. OpenAI (optional)

To use OpenAI for test-step generation:

```bash
export OPENAI_API_KEY="sk-..."
# optional: export OPENAI_MODEL="gpt-4o-mini"
```

If `OPENAI_API_KEY` is not set, the built-in heuristic generator is used (e.g. “Open Settings → Navigate to Wi-Fi → Verify page loads”).

---

## How to run

### Dashboard (Streamlit)

From the project root `ai-qa-agent/`:

```bash
streamlit run app.py
```

Then in the browser:

1. Enter a **bug description** (e.g. “WiFi screen crashes when opened”).
2. Click **Generate Test Steps** to see AI-generated steps.
3. Click **Run iOS Regression Test** and/or **Run Android Regression Test**.
4. View **PASS/FAIL** and **evidence** (screenshot and recording) in the Results section.

### Automation only (no UI)

Run tests from the command line (with Appium and simulator/emulator already running):

```bash
# iOS
python -c "
import sys; sys.path.insert(0, '.')
from automation.ios_test import run_ios_test
r = run_ios_test()
print(r['status'], r.get('screenshot'), r.get('video'))
"

# Android
python -c "
import sys; sys.path.insert(0, '.')
from automation.android_test import run_android_test
r = run_android_test()
print(r['status'], r.get('screenshot'), r.get('video'))
"
```

---

## Configuration

All config is in `config/settings.py`. Override via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `APPIUM_URL` | Appium server URL | `http://127.0.0.1:4723` |
| `IOS_DEVICE_NAME` | iOS Simulator name | `iPhone 16` |
| `IOS_PLATFORM_VERSION` | iOS version | `18.0` |
| `ANDROID_DEVICE_NAME` | Android Emulator name | `Android Emulator` |
| `ANDROID_PLATFORM_VERSION` | Android API level | `14.0` |
| `OPENAI_API_KEY` | OpenAI API key (optional) | — |
| `OPENAI_MODEL` | Model for test steps | `gpt-4o-mini` |

No manual code changes are required; set env vars or edit `config/settings.py` if needed.

---

## Evidence and reports

- **Screenshots:** `evidence/screenshots/ios/` and `evidence/screenshots/android/`.
- **Recordings:** `evidence/recordings/ios/` and `evidence/recordings/android/`.
- **JSON reports:** `reports/<test_name>_<platform>_<timestamp>.json`.

Report shape:

```json
{
  "test_name": "regression_test",
  "platform": "iOS",
  "status": "PASS",
  "screenshot": "/path/to/evidence/screenshots/ios/...",
  "video": "/path/to/evidence/recordings/ios/...",
  "error": null
}
```

---

## License and support

Use and extend as needed for your QA workflow. Ensure Appium and the correct simulator/emulator are running before starting tests.
