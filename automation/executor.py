"""
Test execution engine: reads structured test steps, translates them to Appium commands,
executes on simulator/emulator, and returns PASS/FAIL with evidence paths.
Uses WebDriverWait and retries for stability. Integrates with utils/evidence and logging.
Also used by the chat-driven AI QA agent, which passes a BUG ID to name evidence files.
"""


import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

APPIUM_URL = "http://127.0.0.1:4723"
ELEMENT_WAIT_TIMEOUT = 5
MAX_RETRIES = 2

# Strong success validation: page source must contain at least one marker after login flow.
FINAL_SUCCESS_MARKERS = [
    "inicio",
    "home",
    "bienvenido",
    "dashboard",
    "saldo",
    "cuenta",
]

TARGET_ALIASES = {
    "login": ["Entrar a mi cuenta", "Entrar"],
    "log in": ["Entrar a mi cuenta", "Entrar"],
    "sign in": ["Entrar a mi cuenta", "Entrar"],
    "submit": ["Entrar"],
    "enter": ["Entrar"],
    "register": ["Registrarme"],
    "sign up": ["Registrarme"],
    "signup": ["Registrarme"],
    "phone": ["Teléfono"],
    "phone number": ["Teléfono"],
    "mobile": ["Teléfono"],
    "mobile number": ["Teléfono"],
    "username": ["Teléfono"],
    "password": ["Contraseña"],
    "passcode": ["Contraseña"],
    "home": ["Inicio"],
    "dashboard": ["Inicio"],
    "verification code": ["Código de validación"],
    "validation code": ["Código de validación"],
    "otp": ["Código de validación"],
    "continue": ["Continuar"],
    "more": ["Más"],
    "menu": ["Más"],
}


def format_phone(value: str) -> str:
    """Format 8-digit local numbers as NNNN-NNNN (e.g. 66728317 -> 6672-8317)."""
    value = str(value or "").replace("-", "").strip()
    if len(value) == 8:
        return value[:4] + "-" + value[4:]
    return value


def _uia_text_escape(target: str) -> str:
    """Escape double quotes for UiSelector string literals."""
    return (target or "").replace("\\", "\\\\").replace('"', '\\"')


def _get_input_value(driver, el) -> str:
    """Read best-effort value from an input element (driver reserved for future hooks)."""
    _ = driver
    try:
        for attr in ("value", "text", "name", "label"):
            v = el.get_attribute(attr)
            if v is not None and str(v).strip():
                return str(v).strip()
        return (el.text or "").strip()
    except Exception:
        return ""


def _is_password_field(field: str) -> bool:
    f = (field or "").lower()
    return "pass" in f or "contra" in f or "pwd" in f or "clave" in f


def _is_phone_field(field: str) -> bool:
    f = (field or "").lower()
    return "tel" in f or "phone" in f or "móvil" in f or "movil" in f


def _normalize_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _input_value_accepted(field: str, value: str, entered: str) -> bool:
    """Secure fields often hide text; do not false-fail when value is not visible."""
    if _is_password_field(field):
        return True
    if not value:
        return False
    # Phone: app often shows 66728317 while we type 6672-8317 — compare digits only.
    if _is_phone_field(field):
        vd = _normalize_digits(value)
        ed = _normalize_digits(entered)
        if not vd:
            return False
        if ed == vd:
            return True
        if len(vd) == 8 and ed.startswith(vd):
            return True
        if vd in ed:
            return True
        return False
    return bool(value) and (value in (entered or ""))


def _read_input_with_retries(driver, el, field: str, value: str, max_attempts: int = 5) -> str:
    """Some controls update value asynchronously after send_keys."""
    entered = _get_input_value(driver, el)
    if _input_value_accepted(field, value, entered):
        return entered
    for _ in range(max_attempts - 1):
        time.sleep(0.45)
        entered = _get_input_value(driver, el)
        if _input_value_accepted(field, value, entered):
            return entered
    return entered


def _type_value_gently(el, value: str) -> None:
    """Fallback: one character at a time (more stable on some iOS/Android fields)."""
    for ch in value:
        el.send_keys(ch)
        time.sleep(0.06)


def _phone_digits_visible_in_hierarchy(driver, value: str) -> bool:
    """Last resort: some fields don't expose value via attributes; check flattened hierarchy."""
    vd = _normalize_digits(value)
    if len(vd) < 7:
        return False
    try:
        flat = re.sub(r"\D+", "", driver.page_source or "")
        return vd in flat
    except Exception:
        return False


def _should_skip_tap_target(target: str) -> bool:
    """Do not tap static labels that look like field names (wrong element)."""
    t = (target or "").strip().lower()
    return t in (
        "teléfono",
        "telefono",
        "correo electrónico",
        "correo electronico",
        "correo",
    )


def _candidate_targets(target: str) -> List[str]:
    raw = (target or "").strip()
    if not raw:
        return []

    normalized = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    candidates: List[str] = [raw]
    for alias in TARGET_ALIASES.get(normalized, []):
        if alias not in candidates:
            candidates.append(alias)
    return candidates


def _collect_visible_input_fields(driver, platform: str) -> List:
    """Return visible text inputs in DOM order (phone + password fields)."""
    from appium.webdriver.common.appiumby import AppiumBy

    if platform.lower() == "android":
        fields = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")
    else:
        tf = driver.find_elements(AppiumBy.CLASS_NAME, "XCUIElementTypeTextField")
        sf = driver.find_elements(AppiumBy.CLASS_NAME, "XCUIElementTypeSecureTextField")
        fields = list(tf) + list(sf)

    visible: List = []
    for f in fields:
        try:
            if f.is_displayed():
                visible.append(f)
        except Exception:
            continue
    return visible


def _pick_visible_input_index(field: str, bug_description: str, n_visible: int) -> int:
    """
    Choose field index from visible inputs (login / register / forgot — no hardcoded WiFi flows).
    Falls back safely when fewer fields than expected.
    """
    if n_visible < 1:
        return 0

    def clamp(i: int) -> int:
        return max(0, min(i, n_visible - 1))

    fl = (field or "").lower()
    bd = (bug_description or "").lower()

    # Forgot / reset password: email or phone first screen
    if any(x in bd for x in ("forgot", "olvido", "recuper", "reset")):
        if any(x in fl for x in ("email", "correo", "mail", "@")):
            return clamp(0)
        if _is_phone_field(field):
            return clamp(0)
        if _is_password_field(field):
            return clamp(0)
        return clamp(0)

    # Registration: name / email / phone / password order when multiple fields exist
    if "register" in bd or "registr" in bd:
        if any(x in fl for x in ("nombre", "name", "apellido", "lastname")):
            return clamp(0)
        if any(x in fl for x in ("email", "correo", "mail")):
            return clamp(1) if n_visible > 1 else 0
        if _is_phone_field(field):
            return clamp(2) if n_visible > 2 else clamp(0)
        if _is_password_field(field):
            return clamp(3) if n_visible > 3 else clamp(1)
        return clamp(0)

    # Default login: first field = phone, second = password
    if "telefono" in fl or "phone" in fl or (_is_phone_field(field) and not _is_password_field(field)):
        return clamp(0)
    if "contraseña" in fl or "password" in fl or _is_password_field(field):
        return clamp(1)
    return clamp(0)


def _wait_for_screen_transition(driver, target: str) -> None:
    """Wait for navigation/content change before strict verification."""
    from selenium.webdriver.support.ui import WebDriverWait

    tgt = (target or "").strip()
    if not tgt:
        return
    # Use a longer wait for real screen transitions (login → home).
    long_wait = WebDriverWait(driver, 20)
    try:
        long_wait.until(lambda d: tgt.lower() in d.page_source.lower())
    except Exception:
        time.sleep(3)


def _scroll_gesture_down(driver) -> None:
    try:
        driver.execute_script(
            "mobile: scrollGesture",
            {
                "left": 100,
                "top": 100,
                "width": 400,
                "height": 800,
                "direction": "down",
                "percent": 0.8,
            },
        )
    except Exception:
        pass


def _xpath_escape_for_contains(value: str) -> str:
    """Escape double quotes for XPath string literals."""
    return (value or "").replace('"', '\\"')


def find_element_smart(driver, wait, target: str, platform: str):
    """
    Inspector-style locator order: accessibility id → exact button → partial text/label/name.
    Matches real iOS/Android hierarchy (XCUIElementTypeButton / android.widget.Button).
    """
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    if not (target or "").strip():
        raise ValueError("target required")
    t = str(target).strip()
    safe = _xpath_escape_for_contains(t)

    try:
        return wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, t)))
    except Exception:
        pass

    pl = (platform or "").lower()
    if pl == "ios":
        try:
            return wait.until(
                EC.presence_of_element_located(
                    (
                        AppiumBy.XPATH,
                        f'//XCUIElementTypeButton[contains(@name,"{safe}") or contains(@label,"{safe}") '
                        f'or contains(@value,"{safe}")]',
                    )
                )
            )
        except Exception:
            pass
    else:
        try:
            return wait.until(
                EC.presence_of_element_located(
                    (AppiumBy.XPATH, f'//android.widget.Button[@text="{safe}"]')
                )
            )
        except Exception:
            pass
        try:
            return wait.until(
                EC.presence_of_element_located(
                    (
                        AppiumBy.XPATH,
                        f'//*[@clickable="true" and @text="{safe}"]',
                    )
                )
            )
        except Exception:
            pass

    try:
        return wait.until(
            EC.presence_of_element_located(
                (
                    AppiumBy.XPATH,
                    f'//*[contains(@text,"{safe}") or contains(@label,"{safe}") '
                    f'or contains(@name,"{safe}") or contains(@content-desc,"{safe}")]',
                )
            )
        )
    except Exception:
        pass

    raise Exception(f"Element not found: {target}")


def _hide_keyboard_safe(driver) -> None:
    try:
        driver.hide_keyboard()
    except Exception:
        pass


def _wait_element_interactive(el, timeout: float = 8.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if el.is_displayed() and el.is_enabled():
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise Exception("Element not displayed/enabled in time")


def _tap_with_smart_locator(driver, _wait, target: str, platform: str) -> None:
    """Production tap: smart find, dismiss keyboard, wait interactive, click + gesture fallback."""
    from selenium.webdriver.support.ui import WebDriverWait

    print(f"Clicking: {target}")
    smart_wait = WebDriverWait(driver, 15)
    last_err: Optional[Exception] = None
    el = None
    for cand in _candidate_targets(target):
        try:
            _hide_keyboard_safe(driver)
            el = find_element_smart(driver, smart_wait, cand, platform)
            _wait_element_interactive(el)
            break
        except Exception as e:
            last_err = e
            el = None
    if el is None:
        raise last_err or Exception(f"Element not found: {target}")

    _hide_keyboard_safe(driver)
    try:
        el.click()
    except Exception:
        print("Normal click failed → using fallback")
        try:
            driver.execute_script("mobile: clickGesture", {"elementId": el.id})
        except Exception:
            try:
                center = _ios_element_center(el)
                if center and platform.lower() == "ios":
                    driver.execute_script("mobile: tap", center)
                else:
                    el.click()
            except Exception:
                el.click()

    _wait_after_login_tap(driver, target)

    if _is_login_submit_target(target):
        time.sleep(3)
        page = (driver.page_source or "").lower()
        progressed = (
            "inicio" in page
            or "home" in page
            or "código de validación" in page
            or "codigo de validacion" in page
            or "dashboard" in page
            or "saldo" in page
        )
        still_login_form = ("teléfono" in page or "telefono" in page) and (
            "contraseña" in page or "contrasena" in page
        )
        if not progressed and still_login_form:
            raise Exception("Login failed → still on login screen")


def _verify_element_strict(driver, wait, target: str) -> bool:
    """
    Strict page-level verify (no fake PASS): text must appear in hierarchy after settle time.
    """
    _ = wait
    if not target or not str(target).strip():
        raise ValueError("Target required")
    t = str(target).strip()
    time.sleep(3)
    page = (driver.page_source or "").lower()
    if t.lower() not in page:
        raise Exception(f"{t} not found → FAIL")
    return True


def _final_success_gate(driver) -> None:
    """Raise if post-login shell markers are not present (no false PASS)."""
    page = driver.page_source.lower()
    if not any(marker in page for marker in FINAL_SUCCESS_MARKERS):
        raise Exception("Login did not reach home screen")


def _is_login_submit_target(target: str) -> bool:
    """Targets that submit credentials and need extra time for navigation."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (target or "").strip().lower()).strip()
    return normalized in ("entrar", "login", "log in", "sign in", "submit", "enter")


def _wait_after_login_tap(driver, target: str) -> None:
    """After tapping Entrar/Login/Submit, wait for post-login UI or fall back to delay."""
    if not _is_login_submit_target(target):
        return
    from selenium.webdriver.support.ui import WebDriverWait

    print("Waiting for login response...")
    try:
        # Use generous timeout and allow the OTP/validation screen as an intermediate success state.
        WebDriverWait(driver, 20).until(
            lambda d: (
                "inicio" in d.page_source.lower()
                or "código de validación" in d.page_source.lower()
                or "codigo de validacion" in d.page_source.lower()
            )
        )
    except Exception:
        time.sleep(5)
    _handle_post_login_ios(driver)


def _ios_button_predicates(target: str) -> List[str]:
    t = (target or "").replace("'", "\\'")
    return [
        f"type == 'XCUIElementTypeButton' AND (name CONTAINS '{t}' OR label CONTAINS '{t}' OR value CONTAINS '{t}')",
        f"type == 'XCUIElementTypeStaticText' AND (name CONTAINS '{t}' OR label CONTAINS '{t}' OR value CONTAINS '{t}')",
        f"name CONTAINS '{t}' OR label CONTAINS '{t}' OR value CONTAINS '{t}'",
    ]


def _ios_element_center(el) -> Optional[Dict[str, int]]:
    try:
        rect = el.rect or {}
        x = int(rect.get("x", 0) + (rect.get("width", 0) / 2))
        y = int(rect.get("y", 0) + (rect.get("height", 0) / 2))
        if x > 0 and y > 0:
            return {"x": x, "y": y}
    except Exception:
        return None
    return None


def _tap_ios_with_fallbacks(driver, el, target: str) -> None:
    """
    iOS sometimes exposes the label inside a button instead of the tappable parent.
    Try click first, then coordinate-based native taps at the element center.
    """
    last_error: Optional[Exception] = None
    center = _ios_element_center(el)

    for attempt in (
        "click",
        "mobile_tap",
    ):
        try:
            if attempt == "click":
                el.click()
            elif center and attempt == "mobile_tap":
                driver.execute_script("mobile: tap", center)
            else:
                continue
            _wait_after_login_tap(driver, target)
            return
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error


def _ios_page_contains(driver, text: str) -> bool:
    try:
        return text.lower() in (driver.page_source or "").lower()
    except Exception:
        return False


def _handle_post_login_ios(driver) -> None:
    """
    Handle known post-login interruptions on iOS:
    - "Save Password?" sheet
    - validation-code screen with a visible "Continuar" CTA
    """
    _dismiss_system_alerts_ios(driver)

    if _ios_page_contains(driver, "código de validación") or _ios_page_contains(driver, "codigo de validacion"):
        try:
            from selenium.webdriver.support.ui import WebDriverWait

            wait = WebDriverWait(driver, 8)
            continuar = _find_element_ios(driver, wait, "Continuar")
            _tap_ios_with_fallbacks(driver, continuar, "Continuar")
        except Exception:
            pass
        try:
            WebDriverWait(driver, 20).until(lambda d: "inicio" in (d.page_source or "").lower())
        except Exception:
            time.sleep(3)


def _tap_ios(driver, wait, target: str) -> None:
    """Tap via smart locator stack (Inspector order) + keyboard dismiss + fallbacks."""
    _tap_with_smart_locator(driver, wait, target, "ios")


def _tap_android(driver, wait, target: str) -> None:
    """Tap via smart locator stack + keyboard dismiss + fallbacks."""
    _tap_with_smart_locator(driver, wait, target, "android")


def _wait_for_app_ready(driver) -> None:
    """Ensure app has rendered a non-trivial page tree before steps."""
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        WebDriverWait(driver, 10).until(lambda d: len(d.page_source) > 100)
    except Exception:
        time.sleep(5)


def _splash_stabilize(driver) -> None:
    """Wait for main login UI or fall back to fixed delay."""
    try:
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(driver, 15).until(
            lambda d: (
                ("Teléfono" in d.page_source)
                or ("Telefono" in d.page_source)
                or ("tel" in d.page_source.lower())
                or ("Entrar a mi cuenta" in d.page_source)
                or ("Registrarme" in d.page_source)
            )
        )
    except Exception:
        time.sleep(5)


def _print_page_snippet(driver) -> None:
    try:
        ps = driver.page_source or ""
        print(f"Current page snippet: {ps[:300]}")
    except Exception as ex:
        print(f"Current page snippet: <unavailable: {ex}>")


def _get_logger():
    import logging
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "test_execution.log"
    logger = logging.getLogger("test_execution")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    return logger


def _find_element_ios(driver, wait, target: str):
    """Resolve target to an iOS element with retries. Uses XCUITest locators."""
    from appium.webdriver.common.appiumby import AppiumBy

    if not (target or "").strip():
        raise ValueError("Target is required for element lookup")

    predicates: List[str] = []
    for candidate in _candidate_targets(target):
        predicates.extend(_ios_button_predicates(candidate))

    def _visible_predicate(_driver):
        for pred in predicates:
            els = _driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
            for el in els:
                try:
                    if el.is_displayed():
                        return el
                except Exception:
                    continue
        return False

    # One scroll retry only (deterministic).
    try:
        return wait.until(_visible_predicate)
    except Exception:
        try:
            driver.execute_script("mobile: scroll", {"direction": "down"})
        except Exception:
            pass
        return wait.until(_visible_predicate)


def _find_element_android(driver, wait, target: str):
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    if not (target or "").strip():
        raise ValueError("Missing target in step")

    selectors: List[str] = []
    for candidate in _candidate_targets(target):
        et = _uia_text_escape(candidate)
        rid = re.escape(candidate)
        selectors.extend(
            [
                f'new UiSelector().textContains("{et}")',
                f'new UiSelector().descriptionContains("{et}")',
                f'new UiSelector().resourceIdMatches(".*{rid}.*")',
            ]
        )

    for _ in range(2):
        for sel in selectors:
            try:
                loc = (AppiumBy.ANDROID_UIAUTOMATOR, sel)
                el = wait.until(EC.presence_of_element_located(loc))
                if el.is_displayed():
                    return el
            except Exception:
                continue

        _scroll_gesture_down(driver)

    # XPath fallback (text or content-desc)
    for candidate in _candidate_targets(target):
        safe_sq = candidate.replace("'", "\\'")
        xp = f"//*[contains(@text,'{safe_sq}') or contains(@content-desc,'{safe_sq}')]"
        try:
            el = wait.until(EC.presence_of_element_located((AppiumBy.XPATH, xp)))
            if el.is_displayed():
                return el
        except Exception:
            continue
    raise ValueError(f"Element found for '{target}' but not visible")


def _dismiss_system_alerts_ios(driver) -> None:
    """
    Best-effort dismissal of common iOS system alerts.
    """
    try:
        from appium.webdriver.common.appiumby import AppiumBy
        labels = [
            "Allow",
            "OK",
            "Continue",
            "While Using the App",
            "Don’t Allow",
            "Don't Allow",
            "Not Now",
            "Save",
        ]
        for lbl in labels:
            for by, value in (
                (AppiumBy.ACCESSIBILITY_ID, lbl),
                (AppiumBy.IOS_PREDICATE, f"name CONTAINS '{lbl}' OR label CONTAINS '{lbl}' OR value CONTAINS '{lbl}'"),
            ):
                try:
                    els = driver.find_elements(by, value)
                except Exception:
                    els = []
                if not els:
                    continue
                for el in els:
                    try:
                        if el.is_displayed():
                            el.click()
                            return
                    except Exception:
                        continue
    except Exception:
        return


def _dismiss_system_alerts_android(driver) -> None:
    """
    Best-effort dismissal of common Android runtime permission dialogs.
    """
    try:
        from appium.webdriver.common.appiumby import AppiumBy
        candidates = [
            "Allow",
            "ALLOW",
            "OK",
            "Continue",
            "While using the app",
        ]
        for text in candidates:
            els = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{text}")')
            if els:
                try:
                    els[0].click()
                    return
                except Exception:
                    continue
    except Exception:
        return


def _find_field_ios(driver, wait, field: str):
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    f = field.strip()
    # Try accessibility id or "value" / "label" contains.
    for loc in [
        (AppiumBy.ACCESSIBILITY_ID, f),
        (AppiumBy.IOS_PREDICATE, f"name CONTAINS '{f}' OR label CONTAINS '{f}'"),
        (AppiumBy.IOS_PREDICATE, f"type == 'XCUIElementTypeTextField' AND (name CONTAINS '{f}' OR label CONTAINS '{f}')"),
        (AppiumBy.IOS_PREDICATE, f"type == 'XCUIElementTypeSecureTextField' AND (name CONTAINS '{f}' OR label CONTAINS '{f}')"),
    ]:
        try:
            return wait.until(EC.presence_of_element_located(loc))
        except Exception:
            continue
    return wait.until(EC.presence_of_element_located((AppiumBy.IOS_PREDICATE, f"label CONTAINS '{f}'")))


def _find_field_android(driver, wait, field: str):
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support import expected_conditions as EC

    f = field.strip()
    selectors = [
        f'new UiSelector().textContains("{f}")',
        f'new UiSelector().descriptionContains("{f}")',
        f'new UiSelector().resourceIdMatches(".*{f}.*")',
    ]
    for sel in selectors:
        try:
            return wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, sel)))
        except Exception:
            continue
    # Class-based fallback
    try:
        return wait.until(EC.presence_of_element_located((AppiumBy.CLASS_NAME, "android.widget.EditText")))
    except Exception:
        pass
    # XPath fallback (last resort)
    try:
        xp = f'//*[contains(@text, "{f}")]'
        return wait.until(EC.presence_of_element_located((AppiumBy.XPATH, xp)))
    except Exception:
        return wait.until(
            EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{f}")'))
        )


def _perform_input_by_index(
    driver,
    wait,
    step: Dict[str, Any],
    platform: str,
    bug_description: str,
) -> None:
    """
    Real-world input: pick visible fields by index (phone vs password) and flow context.
    Avoids tapping labels / wrong locators from fuzzy text match.
    """
    _ = wait
    field = (step.get("field") or step.get("target") or "").strip()
    field_lower = field.lower()
    value = str(step.get("value") or "")
    if not field:
        raise ValueError("Field is required for input")
    if "tel" in field_lower:
        value = format_phone(value)

    print(f"Typing into: {field}")
    ctx = (bug_description or "").strip()
    print(f"Value: {value} (flow: {ctx[:120]!r})")

    visible = _collect_visible_input_fields(driver, platform)
    if not visible:
        raise Exception("No visible input fields")

    idx = _pick_visible_input_index(field, bug_description, len(visible))
    target_el = visible[idx]

    target_el.click()
    time.sleep(2)

    try:
        target_el.clear()
    except Exception:
        pass

    for ch in value:
        target_el.send_keys(ch)
        time.sleep(0.1)

    entered = _get_input_value(driver, target_el)
    raw_visible = (target_el.text or target_el.get_attribute("value") or "").strip()
    print(f"Entered value: {entered} (raw: {raw_visible!r})")

    if _input_value_accepted(field, value, entered):
        return
    if _is_phone_field(field) and _phone_digits_visible_in_hierarchy(driver, value):
        return
    if not raw_visible and not _is_password_field(field):
        raise Exception(f"Input failed: {field}")
    if not _is_password_field(field):
        raise Exception(f"Input validation failed for {field}")


def _perform_input_ios(
    driver, wait, step: Dict[str, Any], bug_description: str = ""
) -> None:
    _perform_input_by_index(driver, wait, step, "ios", bug_description)


def _perform_input_android(
    driver, wait, step: Dict[str, Any], bug_description: str = ""
) -> None:
    _perform_input_by_index(driver, wait, step, "android", bug_description)


def _resolve_target(step: Dict[str, Any], elements: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    If YAML uses an element key (e.g. login_button), resolve it to its display value.
    Keeps backwards compatibility with steps that already use literal text targets.
    """
    if not elements:
        return step
    tgt = step.get("target")
    if isinstance(tgt, str) and tgt in elements and isinstance(elements.get(tgt), dict):
        resolved = dict(step)
        resolved["_element"] = elements[tgt]
        # For existing locator logic we keep `target` as the human-facing label/value.
        resolved["target"] = elements[tgt].get("value") or tgt
        # For input actions, map to `field`.
        if resolved.get("action") == "input":
            resolved["field"] = elements[tgt].get("value") or tgt
        return resolved
    return step

def _execute_steps_ios(
    driver,
    steps: List[Dict[str, Any]],
    evidence_prefix: str,
    bug_description: str = "",
) -> tuple[str, Optional[str], Optional[str]]:
    """Execute structured steps on iOS. Returns (status, screenshot_path, video_path)."""
    from selenium.webdriver.support.ui import WebDriverWait
    from utils.evidence import capture_screenshot, start_recording, stop_recording

    wait = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT)
    log = _get_logger()
    screenshot_path: Optional[str] = None
    video_path: Optional[str] = None

    # Splash / initial load: wait for login UI or fixed delay
    try:
        wait.until(lambda d: len(d.page_source) > 0)
    except Exception:
        pass
    _wait_for_app_ready(driver)
    _splash_stabilize(driver)

    for i, step in enumerate(steps):
        print(f"Running step: {step}")
        _print_page_snippet(driver)
        action = (step.get("action") or "").strip().lower()
        target = (step.get("target") or "").strip()
        log.info(f"iOS step {i+1}: action={action}, target={target}")

        try:
            _dismiss_system_alerts_ios(driver)
            if action == "open_app":
                log.info("open_app (no-op; start from home screen / current app)")
            elif action == "start_recording":
                start_recording(driver)
            elif action == "stop_recording":
                video_path = stop_recording(driver, prefix=evidence_prefix, subdir="ios")
            elif action == "tap":
                if not target:
                    raise ValueError("Target is required for tap")
                if _should_skip_tap_target(target):
                    print("Skipping label tap:", target)
                else:
                    print("Looking for:", target)
                    for attempt in range(MAX_RETRIES):
                        try:
                            _tap_ios(driver, wait, target)
                            break
                        except Exception as e:
                            err = str(e).lower()
                            if "disabled" in err:
                                raise
                            if attempt < MAX_RETRIES - 1:
                                _scroll_gesture_down(driver)
                            else:
                                # Last-chance scroll before failing
                                _scroll_gesture_down(driver)
                                raise e
            elif action == "input":
                _perform_input_ios(driver, wait, step, bug_description)
            elif action == "scroll":
                driver.execute_script("mobile: scroll", {"direction": "down"})
            elif action == "verify_element":
                if not target:
                    raise ValueError("Target is required for verify_element")
                print("Looking for:", target)
                try:
                    _verify_element_strict(driver, wait, target)
                except Exception:
                    try:
                        _scroll_gesture_down(driver)
                    except Exception:
                        pass
                    _verify_element_strict(driver, wait, target)
            elif action == "capture_screenshot":
                screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="ios")
            else:
                log.warning(f"Unknown action: {action}")

            # Step delay for stability
            time.sleep(1)
        except Exception as e:
            log.exception(f"Step failed: {e}")
            try:
                screenshot_path = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir="ios")
            except Exception:
                pass
            return "FAIL", screenshot_path, video_path

    if not screenshot_path and steps:
        try:
            screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="ios")
        except Exception:
            pass

    try:
        _final_success_gate(driver)
    except Exception as e:
        log.exception(str(e))
        try:
            screenshot_path = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir="ios")
        except Exception:
            pass
        return "FAIL", screenshot_path, video_path

    return "PASS", screenshot_path, video_path


def _execute_steps_android(
    driver,
    steps: List[Dict[str, Any]],
    evidence_prefix: str,
    bug_description: str = "",
) -> tuple[str, Optional[str], Optional[str]]:
    """Execute structured steps on Android. Returns (status, screenshot_path, video_path)."""
    from selenium.webdriver.support.ui import WebDriverWait
    from utils.evidence import capture_screenshot, start_recording, stop_recording

    wait = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT)
    log = _get_logger()
    screenshot_path: Optional[str] = None
    video_path: Optional[str] = None

    # Splash / initial load: wait for login UI or fixed delay
    try:
        wait.until(lambda d: len(d.page_source) > 0)
    except Exception:
        pass
    _wait_for_app_ready(driver)
    _splash_stabilize(driver)

    for i, step in enumerate(steps):
        print(f"Running step: {step}")
        _print_page_snippet(driver)
        action = (step.get("action") or "").strip().lower()
        target = (step.get("target") or "").strip()
        log.info(f"Android step {i+1}: action={action}, target={target}")

        try:
            _dismiss_system_alerts_android(driver)
            if action == "open_app":
                log.info("open_app (no-op; start from home screen / current app)")
            elif action == "start_recording":
                start_recording(driver)
            elif action == "stop_recording":
                video_path = stop_recording(driver, prefix=evidence_prefix, subdir="android")
            elif action == "tap":
                if not target:
                    raise ValueError("Target is required for tap")
                if _should_skip_tap_target(target):
                    print("Skipping label tap:", target)
                else:
                    print("Looking for:", target)
                    for attempt in range(MAX_RETRIES):
                        try:
                            _tap_android(driver, wait, target)
                            break
                        except Exception as e:
                            err = str(e).lower()
                            if "disabled" in err:
                                raise
                            if attempt < MAX_RETRIES - 1:
                                _scroll_gesture_down(driver)
                            else:
                                # Last-chance scroll before failing
                                _scroll_gesture_down(driver)
                                raise e
            elif action == "input":
                _perform_input_android(driver, wait, step, bug_description)
            elif action == "scroll":
                driver.execute_script("mobile: scrollGesture", {"left": 100, "top": 100, "width": 200, "height": 400, "direction": "down", "percent": 1.0})
            elif action == "verify_element":
                if not target:
                    raise ValueError("Target is required for verify_element")
                print("Looking for:", target)
                try:
                    _verify_element_strict(driver, wait, target)
                except Exception:
                    try:
                        _scroll_gesture_down(driver)
                    except Exception:
                        pass
                    _verify_element_strict(driver, wait, target)
            elif action == "capture_screenshot":
                screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="android")
            else:
                log.warning(f"Unknown action: {action}")

            # Step delay for stability
            time.sleep(1)
        except Exception as e:
            log.exception(f"Step failed: {e}")
            try:
                screenshot_path = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir="android")
            except Exception:
                pass
            return "FAIL", screenshot_path, video_path

    if not screenshot_path and steps:
        try:
            screenshot_path = capture_screenshot(driver, prefix=evidence_prefix, subdir="android")
        except Exception:
            pass

    try:
        _final_success_gate(driver)
    except Exception as e:
        log.exception(str(e))
        try:
            screenshot_path = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir="android")
        except Exception:
            pass
        return "FAIL", screenshot_path, video_path

    return "PASS", screenshot_path, video_path


def run_structured_test(
    platform: str,
    steps: List[Dict[str, Any]],
    bug_description: str = "",
    bug_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run structured test steps on iOS or Android. Returns a result dict for the dashboard and report:
    {
        "timestamp": "...",
        "platform": "iOS" | "Android",
        "bug_description": "...",
        "status": "PASS" | "FAIL",
        "screenshot": path or None,
        "video": path or None,
        "error": message or None,
    }
    """
    import logging
    from datetime import datetime
    from appium import webdriver
    from appium.options.ios import XCUITestOptions
    from appium.options.android import UiAutomator2Options
    from utils.evidence import start_recording, stop_recording

    log = _get_logger()
    ts = datetime.utcnow().isoformat() + "Z"
    result: Dict[str, Any] = {
        "timestamp": ts,
        "platform": platform,
        "bug_description": bug_description,
        "status": "FAIL",
        "screenshot": None,
        "video": None,
        "error": None,
    }
    evidence_prefix = bug_id or f"run_{int(time.time())}"

    if not isinstance(steps, list):
        result["error"] = "Invalid YAML structure: steps must be a list"
        return result

    if not steps:
        result["error"] = "No steps to execute"
        return result

    driver = None
    try:
        if platform.lower() == "ios":
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.device_name = "iPhone 17 Pro"
            options.platform_version = "26.3"
            options.automation_name = "XCUITest"
            # Launch the real app under test.
            options.bundle_id = "com.cwp.app"
            driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
            time.sleep(3)
            # Start recording before first step (chat agent + manual flows).
            start_recording(driver)
            status, screenshot_path, video_path = "FAIL", None, None
            for attempt in range(2):
                if attempt == 1:
                    print("Retrying login once...")
                    time.sleep(2)
                status, screenshot_path, video_path = _execute_steps_ios(
                    driver, steps, evidence_prefix, bug_description
                )
                if status == "PASS":
                    break
            result["video"] = video_path or stop_recording(driver, prefix=evidence_prefix, subdir="ios")
        else:
            options = UiAutomator2Options()
            options.platform_name = "Android"
            options.device_name = "Android Emulator"
            options.automation_name = "UiAutomator2"
            # Launch the real app under test.
            options.app_package = "com.cwp.app"
            options.app_activity = "com.cwp.app.MainActivity"
            driver = webdriver.Remote(command_executor=APPIUM_URL, options=options)
            time.sleep(3)
            start_recording(driver)
            status, screenshot_path, video_path = "FAIL", None, None
            for attempt in range(2):
                if attempt == 1:
                    print("Retrying login once...")
                    time.sleep(2)
                status, screenshot_path, video_path = _execute_steps_android(
                    driver, steps, evidence_prefix, bug_description
                )
                if status == "PASS":
                    break
            result["video"] = video_path or stop_recording(driver, prefix=evidence_prefix, subdir="android")

        result["status"] = status
        result["screenshot"] = screenshot_path
        if status == "FAIL" and not result.get("error"):
            result["error"] = "Test failed (verification, input, or final success gate)"
    except Exception as e:
        log.exception(str(e))
        result["error"] = str(e)
        if driver:
            try:
                from utils.evidence import capture_screenshot
                result["screenshot"] = capture_screenshot(driver, prefix=f"{evidence_prefix}_error", subdir=platform.lower())
                result["video"] = stop_recording(driver, prefix=evidence_prefix, subdir=platform.lower())
            except Exception:
                pass
    finally:
        if driver:
            driver.quit()

    # Write JUnit report for CI/demo
    try:
        from junit_xml import TestSuite, TestCase

        tc = TestCase("AI Test", "Mobile")
        if result.get("status") == "FAIL":
            tc.add_failure_info(result.get("error"))

        ts = TestSuite("Suite", [tc])
        report_path = PROJECT_ROOT / "report.xml"
        with report_path.open("w", encoding="utf-8") as f:
            TestSuite.to_file(f, [ts])
        result["junit_report"] = str(report_path.resolve())
    except Exception:
        pass

    return result


def _copy_evidence_for_bug(
    bug_id: str,
    screenshot_path: Optional[str],
    video_path: Optional[str],
) -> Dict[str, Optional[str]]:
    """
    Copy generic evidence files into BUG-specific names, e.g.:
    evidence/screenshots/BUG-12345.png
    evidence/recordings/BUG-12345.mp4
    """
    if not bug_id:
        return {"screenshot_bug": None, "video_bug": None}

    from utils.evidence import EVIDENCE_SCREENSHOTS, EVIDENCE_RECORDINGS, _ensure_dirs

    _ensure_dirs()
    os.makedirs(EVIDENCE_SCREENSHOTS, exist_ok=True)
    os.makedirs(EVIDENCE_RECORDINGS, exist_ok=True)

    screenshot_bug: Optional[str] = None
    video_bug: Optional[str] = None

    if screenshot_path and Path(screenshot_path).exists():
        dest = EVIDENCE_SCREENSHOTS / f"{bug_id}.png"
        shutil.copyfile(screenshot_path, dest)
        screenshot_bug = str(dest.resolve())

    if video_path and Path(video_path).exists():
        dest = EVIDENCE_RECORDINGS / f"{bug_id}.mp4"
        shutil.copyfile(video_path, dest)
        video_bug = str(dest.resolve())

    return {"screenshot_bug": screenshot_bug, "video_bug": video_bug}


def run_test_case(
    test_case: Dict[str, Any],
    test_data: Optional[Dict[str, Any]] = None,
    bug_id: Optional[str] = None,
    platform: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a YAML-style test case object + JSON test data object.
    This is used by the dashboard upload flow.
    - Reads platform configuration from `ai_qa_agent/config/app_config.yaml` when present.
    - Substitutes variables like `{{phone_number}}` using provided test_data.
    - Delegates execution to `run_structured_test` with parsed steps.
    """
    import yaml

    test_data = test_data or {}

    if not isinstance(test_case.get("steps"), list):
        raise Exception("Invalid YAML structure")

    # Prefer the new production-style config under ai_qa_agent/ if it exists,
    # unless the caller explicitly overrides the platform (chat agent).
    if platform is None:
        cfg_path = PROJECT_ROOT / "ai_qa_agent" / "config" / "app_config.yaml"
        platform = "iOS"
        if cfg_path.exists():
            try:
                cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                p = str(cfg.get("platform", "ios")).strip().lower()
                platform = "iOS" if p == "ios" else "Android"
            except Exception:
                platform = "iOS"

    # Parse and substitute variables using the new engine if available.
    steps = test_case.get("steps", [])
    try:
        from ai_qa_agent.ai_engine.step_parser import parse_steps
        steps = parse_steps(test_case, test_data)
    except Exception:
        # Fallback: raw steps with no substitution (keeps existing system resilient)
        if not isinstance(steps, list):
            raise ValueError("test_case.steps must be a list")

    # If the YAML includes an `elements` section, resolve element keys to labels.
    elements = test_case.get("elements")
    if isinstance(elements, dict):
        steps = [_resolve_target(s, elements) if isinstance(s, dict) else s for s in steps]  # type: ignore[list-item]

    # Flow hints for register / forgot / login (index selection + splash copy in logs)
    bug_desc = " ".join(
        str(x)
        for x in (
            test_case.get("description"),
            test_case.get("module"),
            test_case.get("id"),
        )
        if x
    ).strip()
    result = run_structured_test(platform, steps, bug_description=bug_desc, bug_id=bug_id)
    result["test_case"] = test_case.get("id")
    if bug_id:
        # Copy evidence into BUG-specific filenames for the chat-driven agent.
        bug_paths = _copy_evidence_for_bug(bug_id, result.get("screenshot"), result.get("video"))
        result.update(bug_paths)
        result["bug_id"] = bug_id
    return result
