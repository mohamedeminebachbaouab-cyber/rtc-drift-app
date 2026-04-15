"""
i18n.py — Traductions FR / EN pour toute l'application.
Utilisation : from app.i18n import t
              t("login.title", lang)  →  "RCC App"
"""

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

    # ── Modal ────────────────────────────────────
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

    # ── Lookup (TRU Serial → IMEI) ──────────────────
    "dash.mode_tru": {
        "fr": "TRU Serial",
        "en": "TRU Serial",
    },
    "dash.mode_imei": {
        "fr": "IMEI",
        "en": "IMEI",
    },
    "dash.tru_required_placeholder": {
        "fr": "TRU Serial (requis)",
        "en": "TRU Serial (required)",
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

    # ── Result details ────────────────────────────
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
    """
    Retourne la traduction pour une cle donnee.
    Accepte des kwargs pour le formatage (ex: t("dash.launched", lang, task_id="abc"))
    """
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang, entry.get("fr", key))
    if kwargs:
        text = text.format(**kwargs)
    return text
