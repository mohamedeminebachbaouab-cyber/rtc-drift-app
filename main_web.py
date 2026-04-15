"""
main-web.py — Application Dash autonome dans un seul fichier.
Ce script contient l'interface Dash, la logique de test RTC, les appels Flespi,
le chiffrement des tokens et le lancement PyWebView.
"""

import base64
import hashlib
import io
import json
import logging
import os
import re
import socket
import threading
import time
import uuid
from datetime import datetime

import requests
from cryptography.fernet import Fernet
from dash import Dash, ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from xhtml2pdf import pisa

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

TRANSLATIONS = {
    # Login translations removed because authentication is no longer required.

    # ── Dashboard ────────────────────────────────
    "dash.title": {
        "fr": "RTC Drift Test",
        "en": "RTC Drift Test",
    },
    "dash.imei_label": {
        "fr": "IMEI",
        "en": "IMEI",
    },
    "dash.imei_placeholder": {
        "fr": "IMEI (15 chiffres, commence par 8)",
        "en": "IMEI (15 digits, starts with 8)",
    },
    "dash.imei_error": {
        "fr": "IMEI invalide (15 chiffres, commence par 8)",
        "en": "Invalid IMEI (15 digits, starts with 8)",
    },
    "dash.tru_label": {
        "fr": "TRU Serial (optionnel)",
        "en": "TRU Serial (optional)",
    },
    "dash.tru_placeholder": {
        "fr": "TRU Serial",
        "en": "TRU Serial",
    },
    "dash.tru_required_placeholder": {
        "fr": "TRU Serial (requis)",
        "en": "TRU Serial (required)",
    },
    "dash.launch_btn": {
        "fr": "Lancer le test",
        "en": "Launch Test",
    },
    "dash.launched": {
        "fr": "Test lance (ID: {task_id})",
        "en": "Test launched (ID: {task_id})",
    },
    "dash.session_expired": {
        "fr": "Erreur : token introuvable, redemarrez l'application",
        "en": "Error: token unavailable, please restart the application",
    },
    "dash.no_tasks": {
        "fr": "Aucune tache en cours",
        "en": "No tasks running",
    },

    # ── Table headers ────────────────────────────
    "table.imei": {
        "fr": "IMEI",
        "en": "IMEI",
    },
    "table.tru": {
        "fr": "TRU Serial",
        "en": "TRU Serial",
    },
    "table.step": {
        "fr": "Etape",
        "en": "Step",
    },
    "table.result": {
        "fr": "Resultat",
        "en": "Result",
    },
    "table.details": {
        "fr": "Details",
        "en": "Details",
    },
    "table.view_btn": {
        "fr": "Voir",
        "en": "View",
    },

    # ── Statuts ──────────────────────────────────
    "status.running": {
        "fr": "En cours",
        "en": "Running",
    },
    "status.success": {
        "fr": "Pass",
        "en": "Pass",
    },
    "status.failed": {
        "fr": "Failed",
        "en": "Failed",
    },
    "status.error": {
        "fr": "Erreur",
        "en": "Error",
    },
    "status.unknown": {
        "fr": "Inconnu",
        "en": "Unknown",
    },

    # ── Etapes de test ───────────────────────────
    "step.starting": {
        "fr": "Demarrage...",
        "en": "Starting...",
    },
    "step.check_online": {
        "fr": "Verification connexion (Essai {attempt}/{max})",
        "en": "Check Device Status (Try {attempt}/{max})",
    },
    "step.check_firmware": {
        "fr": "Verification firmware (Essai {attempt}/{max})",
        "en": "Get Firmware Version (Try {attempt}/{max})",
    },
    "step.sending_command": {
        "fr": "Envoi commande",
        "en": "Sending command",
    },
    "step.waiting_result": {
        "fr": "Attente resultat",
        "en": "Waiting for result",
    },
    "step.checking_result": {
        "fr": "Verification resultat (Essai {attempt}/{max})",
        "en": "Checking result (Try {attempt}/{max})",
    },
    "step.done": {
        "fr": "Termine",
        "en": "Done",
    },

    # ── Messages d'attente ───────────────────────
    "wait.online_retry": {
        "fr": "Device offline, tentative {attempt}/{max} ({time})",
        "en": "Device offline, retry {attempt}/{max} ({time})",
    },
    "wait.firmware_retry": {
        "fr": "Echec lecture firmware, tentative {attempt}/{max} ({time})",
        "en": "Firmware read failed, retry {attempt}/{max} ({time})",
    },
    "wait.result": {
        "fr": "Attente resultat ({time} restantes) (Essai {attempt}/{max})",
        "en": "Waiting for result ({time} remaining) (Try {attempt}/{max})",
    },

    # ── Erreurs de tache ─────────────────────────
    "error.device_offline": {
        "fr": "Device offline",
        "en": "Device offline",
    },
    "error.firmware_read": {
        "fr": "Impossible de lire la version firmware",
        "en": "Could not read firmware version",
    },
    "error.firmware_outdated": {
        "fr": "Firmware pas a jour ({current}), veuillez mettre a jour vers {target}",
        "en": "Firmware not up to date ({current}), please update to {target}",
    },
    "error.command_failed": {
        "fr": "Echec envoi commande RTC",
        "en": "Failed to send RTC command",
    },
    "error.no_payload": {
        "fr": "Aucun message recu (payload.text absent)",
        "en": "No message received (payload.text missing)",
    },
    "error.rtc_drift_failed": {
        "fr": "Failed to measure RTC drift",
        "en": "Failed to measure RTC drift",
    },
    "error.unexpected": {
        "fr": "Erreur inattendue : {detail}",
        "en": "Unexpected error: {detail}",
    },

    # ── Modal ──────────────────────────────────
    "modal.title": {
        "fr": "Resultat — IMEI {imei}",
        "en": "Result — IMEI {imei}",
    },
    "modal.unexpected": {
        "fr": "Resultat inattendu :",
        "en": "Unexpected result:",
    },
    "modal.error_detail": {
        "fr": "Detail",
        "en": "Detail",
    },

    # ── Lookup (TRU Serial → IMEI) ───────────────
    "dash.mode_tru": {
        "fr": "TRU Serial",
        "en": "TRU Serial",
    },
    "dash.mode_imei": {
        "fr": "IMEI",
        "en": "IMEI",
    },
    "lookup.no_device": {
        "fr": "Aucun device trouvé pour ce TRU Serial",
        "en": "No device found for this TRU Serial",
    },
    "lookup.found_title": {
        "fr": "{count} device(s) trouvé(s)",
        "en": "{count} device(s) found",
    },
    "lookup.launch_btn": {
        "fr": "Lancer le test RTC",
        "en": "Launch RTC Test",
    },
    "lookup.error": {
        "fr": "Erreur lors de la recherche",
        "en": "Lookup error",
    },

    # ── Result details ─────────────────────────
    "result.passed": {
        "fr": "PASSED",
        "en": "PASSED",
    },
    "result.failed": {
        "fr": "FAILED",
        "en": "FAILED",
    },
    "result.drift_label": {
        "fr": "Drift brut",
        "en": "Raw drift",
    },
    "result.drift_pct_label": {
        "fr": "Drift (%)",
        "en": "Drift (%)",
    },
    "result.test_duration_label": {
        "fr": "Duree du test",
        "en": "Test duration",
    },
    "result.threshold_label": {
        "fr": "Seuil",
        "en": "Threshold",
    },
    "result.test_date_label": {
        "fr": "Date du test",
        "en": "Test date",
    },
    "result.generate_report": {
        "fr": "Generer le rapport",
        "en": "Generate Report",
    },
}


def t(key: str, lang: str = "fr", **kwargs) -> str:
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang, entry.get("fr", key))
    if kwargs:
        text = text.format(**kwargs)
    return text

# ---------------------------------------------------------------------------
# Crypto / tokens
# ---------------------------------------------------------------------------

_ITERATIONS = 600_000
_SALT_LENGTH = 16
_PASSPHRASE_ENV_VAR = "RCC_TOKEN_PASSPHRASE"
_DEFAULT_PASSPHRASE = "rcc_app_default_passphrase"

_ENCRYPTED_TOKENS = {
    "flespi_token": "9DVaCtOuvdUtQo0hKcV70n2YxVudw58dy7h85aWRRFvCGtUhjAgHos3tMXGfabQA"
}


def derive_key(passphrase: str, salt: bytes) -> bytes:
    key = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode(),
        salt=salt,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(key)


def encrypt_token(token: str, passphrase: str) -> str:
    salt = os.urandom(_SALT_LENGTH)
    fernet = Fernet(derive_key(passphrase, salt))
    ciphertext = fernet.encrypt(token.encode()).decode()
    salt_b64 = base64.b64encode(salt).decode()
    return f"{salt_b64}.{ciphertext}"


def decrypt_token(encrypted: str, passphrase: str) -> str:
    if "." not in encrypted:
        return encrypted
    salt_b64, ciphertext = encrypted.split('.', 1)
    salt = base64.b64decode(salt_b64)
    fernet = Fernet(derive_key(passphrase, salt))
    return fernet.decrypt(ciphertext.encode()).decode()


def _get_passphrase() -> str:
    return os.environ.get(_PASSPHRASE_ENV_VAR, _DEFAULT_PASSPHRASE)


def get_tokens(passphrase: str | None = None) -> dict:
    passphrase = passphrase or _get_passphrase()
    tokens = {}
    for token_name, encrypted_value in _ENCRYPTED_TOKENS.items():
        tokens[token_name] = decrypt_token(encrypted_value, passphrase)
    return tokens

# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

VERSION_CIBLE = "03.01.04.Rev.04"
RTC_COMMAND = "rtc_drift_calc:60"

try:
    import pip_system_certs  # noqa: F401 — charge le store certificats Windows
except ImportError:
    raise RuntimeError(
        "pip_system_certs est requis pour la verification TLS. "
        "Installez-le avec : pip install pip_system_certs"
    )


def validate_token(flespi_token: str) -> bool:
    url = "https://flespi.io/auth/info"
    headers = {"Authorization": f"FlespiToken {flespi_token}"}

    try:
        response = requests.get(url, headers=headers, verify=True, timeout=10)
        if response.status_code != 200:
            logger.warning(f"Token Flespi invalide ({response.status_code})")
            return False

        data = response.json()
        token_info = data.get("result", [{}])[0]
        if not token_info.get("enabled", False):
            logger.warning("Token Flespi desactive (enabled=false)")
            return False

        logger.info("Token Flespi valide")
        return True
    except requests.RequestException as e:
        logger.error(f"Validation token : erreur reseau : {e}")
        return False


def lookup_devices_by_serial(tru_serial: str, flespi_token: str) -> list[dict] | None:
    selector = f'telemetry.freezer.serial.number="{tru_serial}"'
    url = f"https://flespi.io/gw/devices/{selector}"
    headers = {"Authorization": f"FlespiToken {flespi_token}"}
    params = {"fields": "id,name,configuration.ident,connected"}

    try:
        response = requests.get(url, headers=headers, params=params, verify=True, timeout=120)
        if response.status_code == 200:
            results = response.json().get("result", [])
            devices = []
            for r in results:
                ident = r.get("configuration.ident") or r.get("configuration", {}).get("ident", "")
                devices.append({
                    "id": r.get("id"),
                    "name": r.get("name", ""),
                    "ident": ident,
                    "connected": r.get("connected", False),
                })
            logger.info(f"Lookup TRU '{tru_serial}' : {len(devices)} device(s) trouvé(s)")
            return devices
        else:
            logger.error(f"Lookup TRU '{tru_serial}' : HTTP {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Lookup TRU '{tru_serial}' : erreur réseau : {e}")
        return None


def check_device_online(imei: str, flespi_token: str) -> bool:
    query = f'{{configuration.ident="{imei}"}}'
    url = f"https://flespi.io/gw/devices/{query}?fields=connected,telemetry.ident"
    headers = {"Authorization": f"FlespiToken {flespi_token}"}

    try:
        response = requests.get(url, headers=headers, verify=True, timeout=15)
        if response.status_code == 200:
            results = response.json().get("result", [])
            if results:
                connected = results[0].get("connected", False)
                logger.info(f"Device {imei} : {'online' if connected else 'offline'}")
                return connected
            logger.warning(f"Device {imei} : aucun resultat retourne par l'API")
            return False
        else:
            logger.error(f"Check online {imei} : HTTP {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"Check online {imei} : erreur reseau : {e}")
        return False


def get_firmware_version(imei: str, flespi_token: str) -> str | None:
    headers = {"Authorization": f"FlespiToken {flespi_token}"}
    data = [{"name": "setting.getver_fmb640.get", "properties": {}}]
    url = f'https://flespi.io/gw/devices/{{configuration.ident="{imei}"}}/commands'

    try:
        response = requests.post(url, headers=headers, json=data, verify=True, timeout=30)
        if response.status_code == 200:
            results = response.json().get("result", [])
            if not results:
                logger.warning(f"Firmware {imei} : aucun resultat")
                return None

            full_response = results[0].get("response", "")
            if not full_response:
                logger.warning(f"Firmware {imei} : reponse vide")
                return None

            ver_start = full_response.find("Ver:")
            imei_start = full_response.find(" IMEI")
            if ver_start == -1 or imei_start == -1:
                logger.warning(
                    f"Firmware {imei} : format de reponse inattendu : {full_response[:100]}"
                )
                return None

            firmware_version = full_response[ver_start + 4 : imei_start].strip()
            logger.info(f"Device {imei} : firmware {firmware_version}")
            return firmware_version

        elif response.status_code == 400:
            logger.warning(f"Firmware {imei} : bad request (device probablement offline)")
            return None
        else:
            logger.error(f"Firmware {imei} : HTTP {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Firmware {imei} : erreur reseau : {e}")
        return None


def send_command(imei: str, flespi_token: str, command: str = RTC_COMMAND) -> bool:
    url = f'https://flespi.io/gw/devices/{{configuration.ident="{imei}"}}/commands-queue'
    headers = {
        "Authorization": f"FlespiToken {flespi_token}",
        "Content-Type": "application/json",
    }
    data = [{"name": "custom", "properties": {"text": command}}]

    try:
        response = requests.post(url, headers=headers, json=data, verify=True, timeout=30)
        if response.status_code == 200:
            logger.info(f"Commande '{command}' envoyee a {imei}")
            return True
        else:
            logger.error(f"Commande {imei} : HTTP {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"Commande {imei} : erreur reseau : {e}")
        return False


def get_last_payload_text(imei: str, flespi_token: str, from_timestamp: int, to_timestamp: int) -> str | None:
    data = {
        "fields": "timestamp,payload.text,ident",
        "filter": "exists('payload.text')",
        "from": from_timestamp,
        "to": to_timestamp,
    }
    device_selector = f'configuration.ident="{imei}"'
    url = f"https://flespi.io/gw/devices/{{{device_selector}}}/messages"
    params = {"data": json.dumps(data)}
    headers = {
        "Authorization": f"FlespiToken {flespi_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, verify=True, params=params, timeout=60)
        if response.status_code == 200:
            messages = response.json().get("result", [])
            logger.info(f"Messages {imei} : {len(messages)} messages trouves entre {from_timestamp} et {to_timestamp}")

            if not messages:
                logger.info(f"Messages {imei} : aucun message avec payload.text dans la fenetre")
                return None

            # Log details of messages for debugging
            for i, msg in enumerate(messages[:5]):  # Log first 5 messages
                ts = msg.get("timestamp", 0)
                has_payload = "payload.text" in msg
                logger.info(f"Message {i+1}: ts={ts}, has_payload={has_payload}, ident={msg.get('ident', 'N/A')}")

            messages.sort(key=lambda m: m.get("timestamp", 0), reverse=True)
            latest_msg = messages[0]
            payload_text = latest_msg.get("payload.text")

            if payload_text:
                logger.info(f"Message {imei} : payload.text recu ({len(str(payload_text))} chars) du message ts={latest_msg.get('timestamp')}")
                return payload_text
            else:
                logger.warning(f"Message {imei} : message le plus recent n'a pas payload.text")
                return None
        else:
            logger.error(f"Messages {imei} : HTTP {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Messages {imei} : erreur reseau : {e}")
        return None

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

_LOGO_B64 = ""
_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "assets", "carrier_logo.png")
if os.path.exists(_logo_path):
    with open(_logo_path, "rb") as _f:
        _LOGO_B64 = base64.b64encode(_f.read()).decode()

REPORT_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>RTC Clock Verification Report</title>

<style>
@page {
  size: A4;
  margin: 15mm;
}

html, body {
  margin: 0;
  padding: 0;
  font-family: Arial, Helvetica, sans-serif;
}

.a4-sheet {
  width: 180mm;
  box-sizing: border-box;
  position: relative;
}

.header {
  text-align: center;
  margin-bottom: 10mm;
}

.logo {
  height: 18mm;
}

h1 {
  font-size: 18pt;
  margin: 5mm 0 8mm 0;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table td {
  padding: 4mm;
  border-bottom: 1px solid #ddd;
  font-size: 11pt;
}

.label {
  font-weight: bold;
  width: 40%;
}

.footer {
  margin-top: 15mm;
  font-size: 9pt;
  text-align: right;
  color: #777;
}

.result-passed {
  font-weight: bold;
  color: #1b5e20;
}

.result-failed {
  font-weight: bold;
  color: #b71c1c;
}
</style>
</head>

<body>

<div class="a4-sheet">

  <div class="header">
    <img class="logo" src="%%LOGO_SRC%%" />
    <h1>RTC Clock Verification</h1>
  </div>

  <table class="table">
    <tr><td class="label">Device</td><td>%%IMEI%%</td></tr>
    <tr><td class="label">TRU Serial</td><td>%%TRU_SERIAL%%</td></tr>
    <tr><td class="label">Test executed on</td><td>%%TEST_DATE%%</td></tr>
    <tr><td class="label">Maximum drift</td><td>%%DRIFT_MS%% ms</td></tr>
    <tr><td class="label">Drift test duration</td><td>60 s</td></tr>
    <tr><td class="label">Drift</td><td>%%DRIFT_PCT%% %</td></tr>
    <tr><td class="label">Result</td><td class="%%RESULT_CLASS%%">%%RESULT_TEXT%%</td></tr>
  </table>

  <div class="footer">
    Official Verification Report
  </div>

</div>

</body>
</html>
"""


def generate_report_html(imei: str, tru_serial: str, result: dict) -> str:
    print("🔥 TEMPLATE HTML ACTIF")

    with open("report_template.html", "r", encoding="utf-8") as f:
        template = f.read()

    drift = result.get("drift", 0)
    drift_pct = (abs(drift) / 60000) * 100
    passed = drift_pct < 0.1

    drift_ts = result.get("last_drift_ts", 0)
    test_date = (
        datetime.fromtimestamp(drift_ts).strftime("%d/%m/%Y %H:%M")
        if drift_ts else datetime.now().strftime("%d/%m/%Y %H:%M")
    )

    replacements = {
        "%%IMEI%%": imei,
        "%%TRU_SERIAL%%": tru_serial,
        "%%TEST_DATE%%": test_date,
        "%%DRIFT_MS%%": str(drift),
        "%%DRIFT_PCT%%": f"{drift_pct:.4f}",
        "%%RESULT_TEXT%%": "PASSED" if passed else "FAILED",
        "%%RESULT_CLASS%%": "result-passed" if passed else "result-failed",
        "%%LOGO_SRC%%": "",  # optionnel
    }

    for k, v in replacements.items():
        template = template.replace(k, str(v))

    return template

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class ObfuscatedBytes:
    __slots__ = ("_xored", "_pad")

    def __init__(self, data: bytes):
        self._pad = os.urandom(len(data))
        self._xored = bytes(a ^ b for a, b in zip(data, self._pad))

    def get(self) -> bytes:
        return bytes(a ^ b for a, b in zip(self._xored, self._pad))

# ---------------------------------------------------------------------------
# Task manager
# ---------------------------------------------------------------------------

STEP_KEYS = [
    "step.check_online",
    "step.check_firmware",
    "step.sending_command",
    "step.waiting_result",
    "step.checking_result",
]

TOTAL_STEPS = len(STEP_KEYS)
STEP_PROGRESS = [2, 4, 5, 5, 95]


class TaskManager:
    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()

    def create_task(self, imei: str, tru_serial: str, tokens: dict) -> str:
        task_id = str(uuid.uuid4())[:8]
        task_state = {
            "task_id": task_id,
            "imei": imei,
            "tru_serial": tru_serial or "\u2014",
            "current_step": "step.starting",
            "step_index": 0,
            "status": "running",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "wait_message": None,
        }
        with self._lock:
            self._tasks[task_id] = task_state
        thread = threading.Thread(target=self._run_sequence, args=(task_id, imei, tokens), daemon=True)
        thread.start()
        logger.info(f"Tache {task_id} lancee pour IMEI {imei}")
        return task_id

    def get_all_tasks(self) -> list[dict]:
        with self._lock:
            return [dict(t) for t in self._tasks.values()]

    def get_task(self, task_id: str) -> dict | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def clear_tasks(self) -> None:
        with self._lock:
            self._tasks.clear()

    def _update(self, task_id: str, **kwargs):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)

    def _set_step(self, task_id: str, step_index: int, progress_override: int | None = None, **step_extra):
        step_key = STEP_KEYS[step_index] if step_index < TOTAL_STEPS else "step.done"
        progress = progress_override if progress_override is not None else (STEP_PROGRESS[step_index] if step_index < TOTAL_STEPS else 100)
        self._update(
            task_id,
            current_step=step_key,
            step_index=step_index,
            progress=progress,
            wait_message=None,
            step_extra=step_extra if step_extra else None,
        )

    def _set_waiting(self, task_id: str, wait_key: str, time_str: str, **extra):
        msg = {"key": wait_key, "time": time_str}
        msg.update(extra)
        self._update(task_id, wait_message=msg)

    def _set_success(self, task_id: str, result):
        drift = result.get("drift", 0) if isinstance(result, dict) else 0
        drift_pct = (abs(drift) / 60000) * 100
        passed = drift_pct < 0.1
        self._update(
            task_id,
            status="success" if passed else "failed",
            current_step="step.done",
            progress=100,
            result=result,
            wait_message=None,
        )

        if passed:
            task = self.get_task(task_id)
        
            if task:
                report_html = generate_report_html(task["imei"], task["tru_serial"], result)

                reports_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "app",
                    "assets",
                    "reports",
                )
                os.makedirs(reports_dir, exist_ok=True)

                safe_filename = re.sub(
                    r"[^A-Za-z0-9_.-]",
                    "_",
                    f"rtc_report_{task_id}_{task['imei']}.html"
                )

                report_path = os.path.join(reports_dir, safe_filename)

                try:
                    with open(report_path, "w", encoding="utf-8") as report_file:
                        report_file.write(report_html)

                    report_url = f"/assets/reports/{safe_filename}?v={int(time.time())}"
                    self._update(task_id, report_path=report_path, report_url=report_url)

                    logger.info(f"Report generated for task {task_id}: {report_path}")

                except OSError as exc:
                    logger.warning(f"Impossible d'ecrire le rapport {report_path}: {exc}")

    def _set_error(self, task_id: str, error_key: str, **extra):
        self._update(
            task_id,
            status="error",
            progress=100,
            error=error_key,
            error_extra=extra,
            wait_message=None,
        )

    def _set_unknown(self, task_id: str, raw_text: str):
        self._update(
            task_id,
            status="unknown",
            current_step="step.done",
            progress=100,
            result=raw_text,
            wait_message=None,
        )

    def _wait_with_countdown(
        self,
        task_id: str,
        seconds: int,
        wait_key: str,
        progress_from: int | None = None,
        progress_to: int | None = None,
        **extra,
    ):
        end_time = time.time() + seconds
        total = seconds
        while time.time() < end_time:
            remaining = int(end_time - time.time())
            elapsed = total - remaining
            minutes = remaining // 60
            secs = remaining % 60
            self._set_waiting(task_id, wait_key, f"{minutes:02d}:{secs:02d}", **extra)
            if progress_from is not None and progress_to is not None:
                pct = int(progress_from + (progress_to - progress_from) * elapsed / total)
                self._update(task_id, progress=pct)
            time.sleep(1)
        self._update(task_id, wait_message=None)

    ONLINE_MAX_RETRIES = 5
    FW_MAX_RETRIES = 2
    RETRY_DELAY = 60
    RESULT_CHECK_TIMES = [61, 66, 73, 82, 95]  # Vérifications plus fréquentes

    def _run_sequence(self, task_id: str, imei: str, tokens: dict):
        flespi_token = tokens["flespi_token"]
        try:
            firmware = None
            device_was_online = False

            for online_attempt in range(1, self.ONLINE_MAX_RETRIES + 1):
                self._set_step(task_id, 0, attempt=online_attempt, max=self.ONLINE_MAX_RETRIES)
                if not check_device_online(imei, flespi_token):
                    logger.info(
                        f"[{task_id}] Offline, attempt {online_attempt}/{self.ONLINE_MAX_RETRIES}"
                    )
                    if online_attempt < self.ONLINE_MAX_RETRIES:
                        self._wait_with_countdown(
                            task_id,
                            self.RETRY_DELAY,
                            "wait.online_retry",
                            attempt=online_attempt,
                            max=self.ONLINE_MAX_RETRIES,
                        )
                    continue

                device_was_online = True
                logger.info(f"[{task_id}] Device online")
                fw_ok = False
                for fw_attempt in range(1, self.FW_MAX_RETRIES + 1):
                    self._set_step(task_id, 1, attempt=fw_attempt, max=self.FW_MAX_RETRIES)
                    firmware = get_firmware_version(imei, flespi_token)
                    if firmware is not None:
                        fw_ok = True
                        break

                    logger.info(
                        f"[{task_id}] FW read failed, attempt {fw_attempt}/{self.FW_MAX_RETRIES}"
                    )
                    if fw_attempt < self.FW_MAX_RETRIES:
                        self._wait_with_countdown(
                            task_id,
                            self.RETRY_DELAY,
                            "wait.firmware_retry",
                            attempt=fw_attempt,
                            max=self.FW_MAX_RETRIES,
                        )

                if fw_ok:
                    break

                logger.info(
                    f"[{task_id}] FW read failed after {self.FW_MAX_RETRIES} tries, retrying online check"
                )
                if online_attempt < self.ONLINE_MAX_RETRIES:
                    self._wait_with_countdown(
                        task_id,
                        self.RETRY_DELAY,
                        "wait.online_retry",
                        attempt=online_attempt,
                        max=self.ONLINE_MAX_RETRIES,
                    )

            if firmware is None:
                if device_was_online:
                    self._set_error(task_id, "error.firmware_read")
                else:
                    self._set_error(task_id, "error.device_offline")
                return

            if firmware != VERSION_CIBLE:
                logger.info(f"[{task_id}] FW {firmware} != {VERSION_CIBLE}, not up to date")
                self._set_error(
                    task_id,
                    "error.firmware_outdated",
                    current=firmware,
                    target=VERSION_CIBLE,
                )
                return

            logger.info(f"[{task_id}] Firmware OK ({firmware})")
            self._set_step(task_id, 2)
            command_sent_ts = int(time.time())
            if not send_command(imei, flespi_token):
                self._set_error(task_id, "error.command_failed")
                return

            payload_text = None
            prev_wait = 0
            max_checks = len(self.RESULT_CHECK_TIMES)
            max_time = self.RESULT_CHECK_TIMES[-1]

            for attempt, check_at in enumerate(self.RESULT_CHECK_TIMES, 1):
                wait_secs = check_at - prev_wait
                t_from = prev_wait / max_time
                t_to = check_at / max_time
                p_from = int(5 + (1 - (1 - t_from) ** 3) * 93)
                p_to = int(5 + (1 - (1 - t_to) ** 3) * 93)

                self._set_step(task_id, 3, progress_override=p_from, attempt=attempt, max=max_checks)
                self._wait_with_countdown(
                    task_id,
                    wait_secs,
                    "wait.result",
                    progress_from=p_from,
                    progress_to=p_to,
                    attempt=attempt,
                    max=max_checks,
                )

                self._set_step(task_id, 4, progress_override=p_to, attempt=attempt, max=max_checks)
                now_ts = int(time.time())
                # Élargir la fenêtre de recherche pour être plus tolérant aux différences de timestamps
                search_from = command_sent_ts - 30  # 30 secondes de tolérance avant
                search_to = now_ts + 30  # 30 secondes de tolérance après
                logger.info(f"[{task_id}] Checking result attempt {attempt}/{max_checks}: window {command_sent_ts} to {now_ts} (extended: {search_from} to {search_to})")
                payload_text = get_last_payload_text(imei, flespi_token, search_from, search_to)

                if payload_text is not None:
                    logger.info(f"[{task_id}] Payload found at attempt {attempt}/{max_checks}!")
                    break
                
                logger.info(f"[{task_id}] No payload found at attempt {attempt}/{max_checks}, will retry...")
                if attempt < max_checks:
                    logger.info(f"[{task_id}] Passing to next attempt {attempt + 1}/{max_checks}")
                    self._set_step(task_id, 3, progress_override=p_to, attempt=attempt + 1, max=max_checks)
                prev_wait = check_at
            if payload_text is None:
                self._set_error(task_id, "error.no_payload")
                return

            if "Failed to measure RTC drift" in str(payload_text):
                self._set_error(task_id, "error.rtc_drift_failed")
                return

            try:
                result_data = json.loads(payload_text)
                if isinstance(result_data, dict) and "drift" in result_data:
                    self._set_success(task_id, result_data)
                    logger.info(f"[{task_id}] RTC OK : {result_data}")
                    return
            except (json.JSONDecodeError, TypeError):
                pass

            logger.warning(f"[{task_id}] Unknown result : {payload_text}")
            self._set_unknown(task_id, str(payload_text))
        except Exception as e:
            logger.exception(f"[{task_id}] Unexpected error")
            self._set_error(task_id, "error.unexpected", detail=str(e))


task_manager = TaskManager()

# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

IMEI_REGEX = re.compile(r"^8\d{14}$")


def layout(lang: str = "en"):
    return html.Div(
        className="dashboard-container",
        children=[
            html.H1(t("dash.title", lang), className="dashboard-title"),
            html.Div(
                className="id-mode-toggle",
                children=[
                    html.Button(
                        t("dash.mode_tru", lang),
                        id="mode-tru-btn",
                        className="id-mode-btn active",
                        n_clicks=0,
                    ),
                    html.Button(
                        t("dash.mode_imei", lang),
                        id="mode-imei-btn",
                        className="id-mode-btn",
                        n_clicks=0,
                    ),
                ],
            ),
            dcc.Store(id="id-mode-store", data="tru"),
            html.Div(
                className="form-card",
                children=[
                    dcc.Input(
                        id="dash-tru-serial",
                        type="text",
                        placeholder=t("dash.tru_required_placeholder", lang),
                        className="form-input",
                    ),
                    dcc.Input(
                        id="dash-imei",
                        type="text",
                        placeholder=t("dash.imei_placeholder", lang),
                        className="form-input",
                        maxLength=15,
                        style={"display": "none"},
                    ),
                    html.Button(
                        t("dash.launch_btn", lang),
                        id="dash-launch-btn",
                        className="btn-primary",
                        disabled=True,
                        n_clicks=0,
                    ),
                ],
            ),
            html.Div(id="dash-launch-message", className="launch-message"),
            html.Div(id="dash-task-table", className="task-table-container"),
            html.Div(
                id="modal-overlay",
                className="modal-overlay hidden",
                children=[
                    html.Div(
                        className="modal-content",
                        children=[
                            html.Div(
                                className="modal-header",
                                children=[
                                    html.H3(id="modal-title", children=""),
                                    html.Button(
                                        "X",
                                        id="modal-close-btn",
                                        className="modal-close",
                                        n_clicks=0,
                                    ),
                                ],
                            ),
                            html.Div(id="modal-body", className="modal-body"),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="lookup-modal-overlay",
                className="modal-overlay hidden",
                children=[
                    html.Div(
                        className="modal-content",
                        children=[
                            html.Div(
                                className="modal-header",
                                children=[
                                    html.H3(id="lookup-modal-title", children=""),
                                    html.Button(
                                        "X",
                                        id="lookup-modal-close-btn",
                                        className="modal-close",
                                        n_clicks=0,
                                    ),
                                ],
                            ),
                            html.Div(id="lookup-modal-body", className="modal-body"),
                        ],
                    ),
                ],
            ),
            dcc.Interval(id="dash-interval", interval=1000, n_intervals=0),
            dcc.Store(id="modal-task-id-store"),
            dcc.Store(id="report-status-store"),
            dcc.Store(id="lookup-devices-store"),
            dcc.Store(id="lookup-tru-store"),
            dcc.Store(id="lookup-selected-imei-store"),
            dcc.Store(id="lookup-launch-store"),
        ],
    )


@callback(
    Output("id-mode-store", "data"),
    Output("mode-tru-btn", "className"),
    Output("mode-imei-btn", "className"),
    Output("dash-tru-serial", "style"),
    Output("dash-imei", "style"),
    Output("dash-tru-serial", "placeholder"),
    Input("mode-tru-btn", "n_clicks"),
    Input("mode-imei-btn", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def toggle_id_mode(tru_clicks, imei_clicks, lang):
    lang = lang or "en"
    triggered = ctx.triggered_id

    if triggered == "mode-imei-btn":
        return (
            "imei",
            "id-mode-btn",
            "id-mode-btn active",
            {"display": "none"},
            {"display": "block"},
            t("dash.tru_placeholder", lang),
        )

    return (
        "tru",
        "id-mode-btn active",
        "id-mode-btn",
        {"display": "block"},
        {"display": "none"},
        t("dash.tru_required_placeholder", lang),
    )


@callback(
    Output("dash-launch-btn", "disabled"),
    Output("dash-imei", "className"),
    Input("dash-imei", "value"),
    Input("dash-tru-serial", "value"),
    Input("id-mode-store", "data"),
)
def validate_input(imei_value, tru_value, mode):
    if mode == "imei":
        if not imei_value:
            return True, "form-input"
        if not IMEI_REGEX.match(imei_value):
            return True, "form-input input-error"
        return False, "form-input"
    else:
        if not tru_value or not tru_value.strip():
            return True, "form-input"
        return False, "form-input"


@callback(
    Output("dash-launch-message", "children"),
    Output("dash-imei", "value", allow_duplicate=True),
    Output("dash-tru-serial", "value", allow_duplicate=True),
    Output("lookup-modal-overlay", "className", allow_duplicate=True),
    Output("lookup-modal-title", "children", allow_duplicate=True),
    Output("lookup-modal-body", "children", allow_duplicate=True),
    Output("lookup-devices-store", "data"),
    Output("lookup-tru-store", "data"),
    Output("lookup-selected-imei-store", "data", allow_duplicate=True),
    Input("dash-launch-btn", "n_clicks"),
    State("dash-imei", "value"),
    State("dash-tru-serial", "value"),
    State("id-mode-store", "data"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def launch_test(n_clicks, imei, tru_serial, mode, lang):
    lang = lang or "en"
    no_modal = ("modal-overlay hidden", "", "", None, None, None)

    if not n_clicks:
        return (no_update,) * 9

    try:
        tokens = get_tokens()
    except Exception:
        return t("dash.session_expired", lang), no_update, no_update, *no_modal

    if not tokens:
        return t("dash.session_expired", lang), no_update, no_update, *no_modal

    if mode == "imei":
        if not imei:
            return (no_update,) * 9
        task_manager.create_task(imei, tru_serial or "", tokens)
        return "", "", "", *no_modal

    if not tru_serial or not tru_serial.strip():
        return (no_update,) * 9

    tru_serial = tru_serial.strip()
    flespi_token = tokens.get("flespi_token", "")
    devices = lookup_devices_by_serial(tru_serial, flespi_token)

    if devices is None:
        return (
            "",
            no_update,
            no_update,
            "modal-overlay visible",
            t("lookup.error", lang),
            html.P(t("lookup.error", lang), className="result-error"),
            None,
            None,
            None,
        )

    if len(devices) == 0:
        return (
            "",
            no_update,
            no_update,
            "modal-overlay visible",
            t("lookup.no_device", lang),
            html.P(
                t("lookup.no_device", lang),
                style={"textAlign": "center", "padding": "1rem"},
            ),
            None,
            None,
            None,
        )

    title = t("lookup.found_title", lang, count=len(devices))
    body = _build_lookup_modal_body(devices, lang, auto_select=(len(devices) == 1))
    devices_data = [{"ident": d["ident"], "name": d["name"], "connected": d["connected"]} for d in devices]
    selected_imei = devices[0]["ident"] if len(devices) == 1 else None

    return (
        "",
        no_update,
        no_update,
        "modal-overlay visible",
        title,
        body,
        devices_data,
        tru_serial,
        selected_imei,
    )


def _build_lookup_modal_body(devices: list[dict], lang: str, auto_select: bool = False):
    device_buttons = []
    for i, dev in enumerate(devices):
        is_selected = auto_select and len(devices) == 1
        btn_class = "lookup-device-btn selected" if is_selected else "lookup-device-btn"
        device_buttons.append(
            html.Button(
                dev["ident"],
                id={"type": "lookup-device-select", "index": i},
                className=btn_class,
                n_clicks=0,
            )
        )

    launch_disabled = not auto_select
    return html.Div(
        children=[
            html.Div(className="lookup-device-list", children=device_buttons),
            html.Button(
                t("lookup.launch_btn", lang),
                id="lookup-launch-btn",
                className="btn-primary",
                disabled=launch_disabled,
                n_clicks=0,
                style={"marginTop": "1rem"},
            ),
        ],
    )


@callback(
    Output("lookup-modal-body", "children", allow_duplicate=True),
    Output("lookup-selected-imei-store", "data"),
    Input({"type": "lookup-device-select", "index": ALL}, "n_clicks"),
    State("lookup-devices-store", "data"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def select_lookup_device(n_clicks_list, devices_data, lang):
    lang = lang or "en"
    if not devices_data or not any(n_clicks_list):
        return no_update, no_update

    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return no_update, no_update

    selected_index = triggered["index"]
    selected_imei = devices_data[selected_index]["ident"]
    device_buttons = []
    for i, dev in enumerate(devices_data):
        is_selected = (i == selected_index)
        btn_class = "lookup-device-btn selected" if is_selected else "lookup-device-btn"
        device_buttons.append(
            html.Button(
                dev["ident"],
                id={"type": "lookup-device-select", "index": i},
                className=btn_class,
                n_clicks=0,
            )
        )

    body = html.Div(
        children=[
            html.Div(className="lookup-device-list", children=device_buttons),
            html.Button(
                t("lookup.launch_btn", lang),
                id="lookup-launch-btn",
                className="btn-primary",
                disabled=False,
                n_clicks=0,
                style={"marginTop": "1rem"},
            ),
        ],
    )

    return body, selected_imei


@callback(
    Output("lookup-modal-overlay", "className", allow_duplicate=True),
    Output("lookup-launch-store", "data"),
    Input("lookup-launch-btn", "n_clicks"),
    State("lookup-selected-imei-store", "data"),
    State("lookup-tru-store", "data"),
    prevent_initial_call=True,
)
def launch_from_lookup(n_clicks, selected_imei, tru_serial):
    if not n_clicks or not selected_imei:
        return no_update, no_update

    try:
        tokens = get_tokens()
    except Exception:
        return no_update, no_update

    if not tokens:
        return no_update, no_update

    task_manager.create_task(selected_imei, tru_serial or "", tokens)
    return "modal-overlay hidden", {"launched": True}


@callback(
    Output("lookup-modal-overlay", "className", allow_duplicate=True),
    Input("lookup-modal-close-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_lookup_modal(n_clicks):
    if not n_clicks:
        return no_update
    return "modal-overlay hidden"


@callback(
    Output("dash-task-table", "children"),
    Input("dash-interval", "n_intervals"),
    State("lang-store", "data"),
)
def update_task_table(n_intervals, lang):
    lang = lang or "en"
    tasks = task_manager.get_all_tasks()
    if not tasks:
        return html.P(t("dash.no_tasks", lang), className="no-tasks")

    STATUS_COLORS = {
        "running": "76, 110, 245",
        "success": "81, 207, 102",
        "failed": "245, 159, 0",
        "error": "255, 107, 107",
        "unknown": "252, 196, 25",
    }

    header = html.Div(
        className="task-row task-header",
        children=[
            html.Span(t("table.imei", lang), className="col-imei"),
            html.Span(t("table.tru", lang), className="col-tru"),
            html.Span(t("table.step", lang), className="col-step"),
            html.Span(t("table.result", lang), className="col-status"),
            html.Span(t("table.details", lang), className="col-result"),
        ],
    )

    rows = [header]
    tasks.sort(key=lambda task: task.get("created_at", ""), reverse=True)
    for task in tasks:
        status_icon = _get_status_icon(task["status"])
        status_text = t(f"status.{task['status']}", lang)
        step_extra = task.get("step_extra") or {}
        step_display = t(task["current_step"], lang, **step_extra)
        wait_msg = task.get("wait_message")
        if wait_msg and isinstance(wait_msg, dict):
            step_display = t(wait_msg["key"], lang, **{k: v for k, v in wait_msg.items() if k != "key"})

        progress = task["progress"]
        color = STATUS_COLORS.get(task["status"], "76, 110, 245")
        row_style = {
            "background": (
                f"linear-gradient(to right, "
                f"rgba({color}, 0.18) 0%, "
                f"rgba({color}, 0.18) calc({progress}% - 4px), "
                f"rgba({color}, 0.36) {progress}%, "
                f"rgba(255,255,255,0.03) calc({progress}% + 4px), "
                f"rgba(255,255,255,0.03) 100%)"
            ),
        }

        result_cell = _build_result_cell(task, lang)
        rows.append(
            html.Div(
                className=f"task-row status-row-{task['status']}",
                style=row_style,
                children=[
                    html.Span(task["imei"], className="col-imei mono"),
                    html.Span(task["tru_serial"], className="col-tru"),
                    html.Span(step_display, className="col-step"),
                    html.Span(status_text, className="col-status"),
                    result_cell,
                ],
            )
        )

    return html.Div(className="task-table", children=rows)


def _get_status_icon(status: str) -> str:
    icons = {
        "running": "⏳",
        "success": "✅",
        "failed": "❌",
        "error": "⚠️",
        "unknown": "❓",
    }
    return icons.get(status, "❓")


def _build_result_cell(task: dict, lang: str):
    if task["status"] == "running":
        return html.Span("...", className="col-result")

    if task["status"] == "success" or task["status"] == "failed":
        result = task.get("result") or {}
        drift = result.get("drift", "—")
        children = [html.Span(str(drift), className="col-result")]
        report_url = task.get("report_url")
        if report_url:
            children.append(
                html.A(
                    t("result.generate_report", lang),
                    href=report_url,
                    target="_blank",
                    className="report-link",
                    style={
                        "display": "inline-flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "padding": "0.35rem 0.9rem",
                        "background": "#ffffff",
                        "color": "#000000",
                        "border": "1px solid #d0d0d0",
                        "borderRadius": "8px",
                        "textDecoration": "none",
                        "fontSize": "0.85rem",
                        "fontWeight": "700",
                        "boxShadow": "0 0 8px rgba(0, 0, 0, 0.08)",
                    },
                )
            )
        else:
            button = html.Button(
                t("table.view_btn", lang),
                id={"type": "view-result-btn", "index": task["task_id"]},
                className="view-btn",
                n_clicks=0,
            )
            children.append(button)
        return html.Div(children=children)

    if task["status"] == "error":
        error = task.get("error") or "error.unexpected"
        return html.Span(t(error, lang, **(task.get("error_extra") or {})), className="error-result")

    if task["status"] == "unknown":
        return html.Span(str(task.get("result") or ""), className="col-result")

    return html.Span("—", className="col-result")

# ---------------------------------------------------------------------------
# Dash app factory
# ---------------------------------------------------------------------------


def create_app() -> Dash:
    assets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "assets")
    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="RCC App",
        assets_folder=assets_path,
    )

    task_manager.clear_tasks()

    app.layout = html.Div(
        children=[
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="lang-store", data="en", storage_type="local"),
            html.Div(id="page-content"),
        ]
    )

    @callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
        Input("lang-store", "data"),
    )
    def display_page(pathname, lang):
        return layout(lang or "en")

    return app


def main():
    """
    Lance le serveur Dash en mode web pur.
    Accessible via http://localhost:8050 ou http://<machine-ip>:8050
    """
    # Nettoyer toutes les tâches précédentes au démarrage
    task_manager.clear_tasks()
    # Nettoyer aussi l'instance utilisée par le dashboard
    from app.tasks import task_manager as app_task_manager
    app_task_manager.clear_tasks()
    logger.info("Nettoyage des tâches précédentes effectué")
    
    port = int(os.environ.get("RCC_PORT", 8050))
    host = os.environ.get("RCC_HOST", "0.0.0.0")
    
    app = create_app()
    logger.info(f"Démarrage du serveur web sur http://{host}:{port}")
    logger.info(f"URL locale : http://localhost:{port}")
    
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
