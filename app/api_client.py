"""
api_client.py — Wrapper pour les appels API Flespi.
Adapte des fonctions de fragments.py pour un usage device-par-device.
"""

import requests
import logging
import json
import time

try:
    import pip_system_certs  # noqa: F401 — charge le store certificats Windows
except ImportError:
    raise RuntimeError(
        "pip_system_certs est requis pour la verification TLS. "
        "Installez-le avec : pip install pip_system_certs"
    )

logger = logging.getLogger(__name__)

# ── Constantes ──────────────────────────────────
VERSION_CIBLE = "03.01.04.Rev.04"
RTC_COMMAND = "rtc_drift_calc:60"


# ══════════════════════════════════════════════════
#  VALIDATION TOKEN
# ══════════════════════════════════════════════════

def validate_token(flespi_token: str) -> bool:
    """
    Verifie la validite du token Flespi via /auth/info.
    Le status HTTP est toujours 200, on verifie le champ 'enabled' dans le body.
    """
    url = "https://flespi.io/auth/info"
    headers = {"Authorization": f"FlespiToken {flespi_token}"}

    try:
        response = requests.get(
            url, headers=headers, verify=True, timeout=10
        )
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


# ══════════════════════════════════════════════════
#  CHECK DEVICE ONLINE
# ══════════════════════════════════════════════════

def lookup_devices_by_serial(tru_serial: str, flespi_token: str) -> list[dict] | None:
    """
    Recherche les devices par TRU Serial (telemetry.freezer.serial.number).
    Retourne une liste de dicts [{id, name, ident, connected}, ...] ou None en cas d'erreur.
    """
    selector = f'telemetry.freezer.serial.number="{tru_serial}"'
    url = f"https://flespi.io/gw/devices/{selector}"
    headers = {"Authorization": f"FlespiToken {flespi_token}"}
    params = {"fields": "id,name,configuration.ident,connected"}

    try:
        response = requests.get(
            url, headers=headers, params=params, verify=True, timeout=120
        )
        if response.status_code == 200:
            results = response.json().get("result", [])
            devices = []
            for r in results:
                # configuration.ident peut etre retourne en dot-notation ou imbrique
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
    """
    Verifie si un device est connecte via l'API Flespi.
    Retourne True si online, False sinon.
    """
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


# ══════════════════════════════════════════════════
#  CHECK FIRMWARE VERSION
# ══════════════════════════════════════════════════

def get_firmware_version(imei: str, flespi_token: str) -> str | None:
    """
    Recupere la version firmware d'un device via la commande getver.
    Retourne la version sous forme de string (ex: "03.01.04.Rev.04") ou None.

    Le parsing extrait le texte entre "Ver:" et " IMEI" dans la reponse.
    """
    headers = {"Authorization": f"FlespiToken {flespi_token}"}
    data = [{"name": "setting.getver_fmb640.get", "properties": {}}]
    url = f'https://flespi.io/gw/devices/{{configuration.ident="{imei}"}}/commands'

    try:
        response = requests.post(
            url, headers=headers, json=data, verify=True, timeout=30
        )
        if response.status_code == 200:
            results = response.json().get("result", [])
            if not results:
                logger.warning(f"Firmware {imei} : aucun resultat")
                return None

            full_response = results[0].get("response", "")
            if not full_response:
                logger.warning(f"Firmware {imei} : reponse vide")
                return None

            # Parsing adapte au format FMC640 : "Ver:03.01.04.Rev.04 IMEI:867..."
            ver_start = full_response.find("Ver:")
            imei_start = full_response.find(" IMEI")

            if ver_start == -1 or imei_start == -1:
                logger.warning(
                    f"Firmware {imei} : format de reponse inattendu : "
                    f"{full_response[:100]}"
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


# ══════════════════════════════════════════════════
#  SEND CUSTOM COMMAND
# ══════════════════════════════════════════════════

def send_command(imei: str, flespi_token: str, command: str = RTC_COMMAND) -> bool:
    """
    Envoie une commande custom a un device via Flespi commands-queue.
    Retourne True si la commande est envoyee, False sinon.
    """
    url = f'https://flespi.io/gw/devices/{{configuration.ident="{imei}"}}/commands-queue'
    headers = {
        "Authorization": f"FlespiToken {flespi_token}",
        "Content-Type": "application/json",
    }
    data = [{"name": "custom", "properties": {"text": command}}]

    try:
        response = requests.post(
            url, headers=headers, json=data, verify=True, timeout=30
        )
        if response.status_code == 200:
            logger.info(f"Commande '{command}' envoyee a {imei}")
            return True
        else:
            logger.error(f"Commande {imei} : HTTP {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"Commande {imei} : erreur reseau : {e}")
        return False


# ══════════════════════════════════════════════════
#  GET MESSAGES (pour lire payload.text)
# ══════════════════════════════════════════════════

def get_last_payload_text(
    imei: str,
    flespi_token: str,
    from_timestamp: int,
    to_timestamp: int,
) -> str | None:
    """
    Recupere le dernier message contenant payload.text pour un device
    dans l'intervalle de temps donne.
    Retourne le contenu de payload.text ou None si aucun message.
    """
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
        response = requests.get(
            url, headers=headers, verify=True, params=params, timeout=60
        )
        if response.status_code == 200:
            messages = response.json().get("result", [])
            if not messages:
                logger.info(f"Messages {imei} : aucun message avec payload.text")
                return None

            # Trier par timestamp decroissant, prendre le dernier
            messages.sort(key=lambda m: m.get("timestamp", 0), reverse=True)
            payload_text = messages[0].get("payload.text")
            logger.info(f"Message {imei} : payload.text recu ({len(str(payload_text))} chars)")
            return payload_text
        else:
            logger.error(f"Messages {imei} : HTTP {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Messages {imei} : erreur reseau : {e}")
        return None
