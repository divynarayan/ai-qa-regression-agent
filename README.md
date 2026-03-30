# AI QA Regression Testing Agent

A professional QA automation platform that turns **bug descriptions** into **executable regression tests** for iOS and Android. Describe a bug in plain language; the agent generates structured test steps, runs them via Appium on simulators/emulators, and captures screenshots and recordings as evidence.

---

## Project Overview

The AI QA Regression Testing Agent bridges natural-language bug reports and mobile test automation. You enter a bug description (e.g. *"WiFi screen crashes when opened"*); the system:

1. **Generates** structured, executable test steps (JSON) from the description  
2. **Runs** those steps on iOS Simulator or Android Emulator via Appium  
3. **Captures** evidence (screenshots, optional screen recordings)  
4. **Reports** PASS/FAIL with links to evidence and stores run history  

The **Streamlit dashboard** is the main interface: you manage bug descriptions, generate steps, trigger iOS/Android runs, and view results and the last 5 test runs in one place.

---

## Features

- **Natural-language test generation** — Convert bug descriptions into structured test steps (e.g. `open_app`, `tap`, `verify_element`, `capture_screenshot`) without writing code  
- **Dual-platform execution** — Run the same flow on **iOS Simulator** (XCUITest) and **Android Emulator** (UiAutomator2)  
- **Structured executor** — `automation/executor.py` interprets JSON steps, uses WebDriverWait and retries for stability  
- **Evidence collection** — Screenshots and optional screen recordings saved under `evidence/` and `reports/`  
- **Test history** — Last 5 runs persisted under `reports/history/` and shown in the dashboard  
- **System status** — Sidebar shows Appium server, iOS Simulator, and Android Emulator status  
- **Legacy scripts** — Standalone `ios_test.py` (and Android module) for quick runs without the dashboard  

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Streamlit Dashboard (ui/dashboard.py)             │
│  Bug description → Generate steps → Run iOS / Android → Results & History│
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                          │
         ▼                    ▼                          ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐
│ ai_engine/      │  │ automation/       │  │ reports/                     │
│ - bug_parser    │  │ - executor.py     │  │ - history.py (save/load)    │
│ - structured_   │  │ - appium_client   │  │ - screenshots, recordings   │
│   steps         │  │ - runner          │  └─────────────────────────────┘
│ - test_step_    │  └──────────────────┘
│   generator     │           │
└─────────────────┘           ▼
                      Appium Server (127.0.0.1:4723)
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
       iOS Simulator                      Android Emulator
       (XCUITest)                         (UiAutomator2)
```

- **`ai_engine/`** — Bug parsing and generation of executable step JSON  
- **`automation/`** — Appium client, structured step executor, and platform-specific element resolution  
- **`utils/evidence.py`** — Screenshot and screen-recording capture  
- **`reports/`** — Screenshots, recordings, and JSON run history  

---

## Installation

### Prerequisites

- **Python 3.10+**  
- **Appium 2.x** with drivers: `appium driver install xcuitest` and `appium driver install uiautomator2`  
- **Xcode** (for iOS): simulators and `xcrun simctl`  
- **Android SDK** (for Android): `adb` and an AVD  

### 1. Clone and enter the project

```bash
cd /path/to/ai-regression-agent
```

### 2. Run the setup script (recommended)

The script creates a virtual environment, activates it, and installs all dependencies:

```bash
chmod +x setup.sh
./setup.sh
```

This installs: `fastapi`, `uvicorn`, `streamlit`, `openai`, `pandas`, `appium-python-client`, `python-dotenv`, `pillow`, `sqlalchemy`, `pydantic`, `python-multipart`, `requests`, and upgrades `pip`.

### 3. Or install manually

```bash
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install fastapi "uvicorn[standard]" streamlit openai pandas appium-python-client python-dotenv pillow sqlalchemy pydantic python-multipart requests
```

### 4. Start Appium and a device

- Start the Appium server (default: `http://127.0.0.1:4723`):

  ```bash
  appium
  ```

- **iOS:** Boot a simulator, e.g. `open -a Simulator` and choose an iPhone (e.g. iPhone 17 Pro).  
- **Android:** Start an AVD and ensure `adb devices` lists it.

---

## How to Run the Dashboard

1. Activate the virtual environment (if not already):

   ```bash
   source venv/bin/activate
   ```

2. Start the Streamlit dashboard:

   ```bash
   streamlit run ui/dashboard.py
   ```

   Or from the project root:

   ```bash
   streamlit run app.py
   ```

   (`app.py` delegates to `ui/dashboard.py`.)

3. Open the URL shown in the terminal (usually **http://localhost:8501**).

4. In the dashboard:
   - Enter a **bug description** (e.g. *"WiFi screen crashes when opened"*).
   - Click **Generate Test Steps** to get executable JSON.
   - Click **Run iOS Regression Test** or **Run Android Regression Test** to execute.
   - View **Results & Evidence** (PASS/FAIL, screenshot, recording) and **Test History (last 5 runs)**.

---

## How to Run the iOS Regression Test

### Option A: From the dashboard (recommended)

1. Run the dashboard (see above).  
2. Enter a bug description and click **Generate Test Steps**.  
3. Click **Run iOS Regression Test**.  
   - If steps were generated, the **structured executor** runs them.  
   - If not, the dashboard falls back to the legacy **`ios_test.py`** script.

### Option B: Standalone script (no dashboard)

1. Ensure **Appium** is running at `http://127.0.0.1:4723`.  
2. Boot an **iOS Simulator** (e.g. iPhone 16e).  
3. From the project root, with the venv activated:

   ```bash
   python ios_test.py
   ```

   The script opens **Settings → Wi-Fi**, takes a screenshot, and prints `PASS` or `FAIL` (exit code 0 or 1). Screenshots are written to `reports/screenshots/` (e.g. `ios_wifi_settings.png`, or `ios_wifi_error.png` on failure).

4. **Optional:** Adjust `DEVICE_NAME` and `IOS_VERSION` at the top of `ios_test.py` to match your simulator.

---

## Project structure (key paths)

| Path | Purpose |
|------|--------|
| `ui/dashboard.py` | Streamlit UI: bug input, step generation, run buttons, results, history |
| `app.py` | Entry point that runs the dashboard |
| `ai_engine/test_step_generator.py` | Converts bug description → executable steps |
| `ai_engine/structured_steps.py` | Heuristic generation of step JSON for executor |
| `automation/executor.py` | Runs structured steps on iOS/Android, returns PASS/FAIL + evidence |
| `ios_test.py` | Standalone iOS Settings → Wi-Fi test (Appium) |
| `reports/history.py` | Save/load last N run reports (JSON) |
| `utils/evidence.py` | Screenshot and screen recording capture |
| `setup.sh` | One-command venv + dependency setup |

---

## Configuration

- **Appium URL:** Default is `http://127.0.0.1:4723` (set in `dashboard.py`, `executor.py`, and `ios_test.py`).  
- **iOS device/version:** In `ios_test.py` and `executor.py`, set `DEVICE_NAME` / `platform_version` to match your simulator (e.g. iPhone 17 Pro, 26.3).  
- **Android:** Executor uses `com.android.settings`; use an AVD with Settings available.

---

## License

See the repository for license information.
