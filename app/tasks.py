"""
tasks.py — Logique metier : sequence de test RTC en 5 etapes.
Chaque tache tourne dans un thread separe.
L'etat est stocke dans un dictionnaire thread-safe.
Les textes sont des cles i18n, traduits cote dashboard.
"""

import threading
import time
import json
import logging
import uuid
from datetime import datetime

from app.api_client import (
    VERSION_CIBLE,
    check_device_online,
    get_firmware_version,
    send_command,
    get_last_payload_text,
)

logger = logging.getLogger(__name__)

# Cles i18n des etapes (traduites cote dashboard)
STEP_KEYS = [
    "step.check_online",
    "step.check_firmware",
    "step.sending_command",
    "step.waiting_result",
    "step.checking_result",
]

TOTAL_STEPS = len(STEP_KEYS)

# Progression fixe par etape (check_online, check_fw, sending, waiting, checking)
STEP_PROGRESS = [2, 4, 5, 5, 95]


class TaskManager:
    """
    Gestionnaire de taches thread-safe.
    Stocke l'etat de chaque tache dans un dict protege par un Lock.
    """

    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()

    def create_task(self, imei: str, tru_serial: str, tokens: dict) -> str:
        """Cree une nouvelle tache et lance le thread de test."""
        task_id = str(uuid.uuid4())[:8]

        task_state = {
            "task_id": task_id,
            "imei": imei,
            "tru_serial": tru_serial or "\u2014",
            "current_step": "step.starting",  # cle i18n
            "step_index": 0,
            "status": "running",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            # wait_message : None ou {"key": "wait.result", "time": "01:15"}
            "wait_message": None,
        }

        with self._lock:
            self._tasks[task_id] = task_state

        thread = threading.Thread(
            target=self._run_sequence,
            args=(task_id, imei, tokens),
            daemon=True,
        )
        thread.start()
        logger.info(f"Tache {task_id} lancee pour IMEI {imei}")
        return task_id

    def get_all_tasks(self) -> list[dict]:
        """Retourne la liste de toutes les taches (copie thread-safe)."""
        with self._lock:
            return [dict(t) for t in self._tasks.values()]

    def get_task(self, task_id: str) -> dict | None:
        """Retourne l'etat d'une tache par son ID."""
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def clear_tasks(self) -> None:
        """Nettoie toutes les taches en cours."""
        with self._lock:
            self._tasks.clear()

    def _update(self, task_id: str, **kwargs):
        """Met a jour les champs d'une tache."""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)

    def _set_step(self, task_id: str, step_index: int, progress_override: int | None = None, **step_extra):
        """Met a jour l'etape courante et la progression.
        progress_override permet de forcer une valeur de progression.
        step_extra peut contenir attempt/max pour afficher Try X/Y."""
        step_key = STEP_KEYS[step_index] if step_index < TOTAL_STEPS else "step.done"
        if progress_override is not None:
            progress = progress_override
        else:
            progress = STEP_PROGRESS[step_index] if step_index < TOTAL_STEPS else 100
        self._update(
            task_id,
            current_step=step_key,
            step_index=step_index,
            progress=progress,
            wait_message=None,
            step_extra=step_extra if step_extra else None,
        )

    def _set_waiting(self, task_id: str, wait_key: str, time_str: str, **extra):
        """Met a jour le message d'attente (cle i18n + countdown)."""
        msg = {"key": wait_key, "time": time_str}
        msg.update(extra)
        self._update(task_id, wait_message=msg)

    def _set_success(self, task_id: str, result):
        # Determiner si le test RTC est passe ou echoue
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

    def _set_error(self, task_id: str, error_key: str, **extra):
        """Marque la tache comme echouee. error_key est une cle i18n."""
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

    # ── Attente avec countdown ──────────────────
    def _wait_with_countdown(
        self, task_id: str, seconds: int, wait_key: str,
        progress_from: int | None = None, progress_to: int | None = None,
        **extra,
    ):
        """Attend N secondes en mettant a jour le countdown.
        Si progress_from/to sont fournis, la barre progresse lineairement."""
        end_time = time.time() + seconds
        total = seconds
        while time.time() < end_time:
            remaining = int(end_time - time.time())
            elapsed = total - remaining
            minutes = remaining // 60
            secs = remaining % 60
            self._set_waiting(
                task_id, wait_key, f"{minutes:02d}:{secs:02d}", **extra
            )
            if progress_from is not None and progress_to is not None:
                pct = int(progress_from + (progress_to - progress_from) * elapsed / total)
                self._update(task_id, progress=pct)
            time.sleep(1)
        self._update(task_id, wait_message=None)

    # ══════════════════════════════════════════════
    #  SEQUENCE DE TEST (5 etapes)
    # ══════════════════════════════════════════════

    # ── Retry constants ──────────────────────────
    ONLINE_MAX_RETRIES = 5
    FW_MAX_RETRIES = 2
    RETRY_DELAY = 60  # secondes entre chaque retry
    RESULT_CHECK_TIMES = [61, 66, 73, 82, 95]  # secondes cumulees depuis l'envoi

    def _run_sequence(self, task_id: str, imei: str, tokens: dict):
        flespi_token = tokens["flespi_token"]

        try:
            # ── Etapes 1-2 : Check online + firmware (nested retry) ──
            firmware = None
            device_was_online = False

            for online_attempt in range(1, self.ONLINE_MAX_RETRIES + 1):
                # ── Etape 1 : Check device online ──
                self._set_step(task_id, 0,
                               attempt=online_attempt,
                               max=self.ONLINE_MAX_RETRIES)

                if not check_device_online(imei, flespi_token):
                    logger.info(
                        f"[{task_id}] Offline, attempt "
                        f"{online_attempt}/{self.ONLINE_MAX_RETRIES}"
                    )
                    if online_attempt < self.ONLINE_MAX_RETRIES:
                        self._wait_with_countdown(
                            task_id, self.RETRY_DELAY,
                            "wait.online_retry",
                            attempt=online_attempt,
                            max=self.ONLINE_MAX_RETRIES,
                        )
                    continue  # next online attempt

                device_was_online = True
                logger.info(f"[{task_id}] Device online")

                # ── Etape 2 : Check firmware (2 tries per online check) ──
                fw_ok = False
                for fw_attempt in range(1, self.FW_MAX_RETRIES + 1):
                    self._set_step(task_id, 1,
                                   attempt=fw_attempt,
                                   max=self.FW_MAX_RETRIES)

                    firmware = get_firmware_version(imei, flespi_token)

                    if firmware is not None:
                        fw_ok = True
                        break

                    logger.info(
                        f"[{task_id}] FW read failed, attempt "
                        f"{fw_attempt}/{self.FW_MAX_RETRIES}"
                    )
                    if fw_attempt < self.FW_MAX_RETRIES:
                        self._wait_with_countdown(
                            task_id, self.RETRY_DELAY,
                            "wait.firmware_retry",
                            attempt=fw_attempt,
                            max=self.FW_MAX_RETRIES,
                        )

                if fw_ok:
                    break  # got firmware, exit outer loop

                # Both FW attempts failed → go back to online check
                logger.info(
                    f"[{task_id}] FW read failed after "
                    f"{self.FW_MAX_RETRIES} tries, retrying online check"
                )
                if online_attempt < self.ONLINE_MAX_RETRIES:
                    self._wait_with_countdown(
                        task_id, self.RETRY_DELAY,
                        "wait.online_retry",
                        attempt=online_attempt,
                        max=self.ONLINE_MAX_RETRIES,
                    )

            # ── All retries exhausted? ──
            if firmware is None:
                if device_was_online:
                    self._set_error(task_id, "error.firmware_read")
                else:
                    self._set_error(task_id, "error.device_offline")
                return

            if firmware != VERSION_CIBLE:
                logger.info(f"[{task_id}] FW {firmware} != {VERSION_CIBLE}, not up to date")
                self._set_error(
                    task_id, "error.firmware_outdated",
                    current=firmware, target=VERSION_CIBLE,
                )
                return

            logger.info(f"[{task_id}] Firmware OK ({firmware})")

            # ── Etape 3 : Sending command ───────────
            self._set_step(task_id, 2)
            command_sent_ts = int(time.time())
            if not send_command(imei, flespi_token):
                self._set_error(task_id, "error.command_failed")
                return

            # ── Etapes 4-5 : Waiting + Checking result (retry) ──
            payload_text = None
            prev_wait = 0
            max_checks = len(self.RESULT_CHECK_TIMES)
            max_time = self.RESULT_CHECK_TIMES[-1]

            for attempt, check_at in enumerate(self.RESULT_CHECK_TIMES, 1):
                wait_secs = check_at - prev_wait

                # Ease-out cubic : la barre remplit plus vite au debut
                t_from = prev_wait / max_time
                t_to = check_at / max_time
                p_from = int(5 + (1 - (1 - t_from) ** 3) * 93)
                p_to = int(5 + (1 - (1 - t_to) ** 3) * 93)

                self._set_step(task_id, 3, progress_override=p_from,
                               attempt=attempt, max=max_checks)
                self._wait_with_countdown(
                    task_id, wait_secs, "wait.result",
                    progress_from=p_from, progress_to=p_to,
                    attempt=attempt, max=max_checks,
                )

                self._set_step(task_id, 4, progress_override=p_to,
                               attempt=attempt, max=max_checks)
                now_ts = int(time.time())
                search_from = command_sent_ts - 30
                search_to = now_ts + 30
                logger.info(
                    f"[{task_id}] Checking result attempt {attempt}/{max_checks}: "
                    f"window {command_sent_ts} to {now_ts} "
                    f"(extended: {search_from} to {search_to})"
                )
                payload_text = get_last_payload_text(
                    imei, flespi_token, search_from, search_to
                )

                if payload_text is not None:
                    logger.info(f"[{task_id}] Payload found at attempt {attempt}/{max_checks}!")
                    break

                logger.info(
                    f"[{task_id}] No payload found at attempt {attempt}/{max_checks}, will retry..."
                )
                if attempt < max_checks:
                    logger.info(
                        f"[{task_id}] Passing to next attempt {attempt + 1}/{max_checks}"
                    )
                    self._set_step(task_id, 3, progress_override=p_to,
                                   attempt=attempt + 1, max=max_checks)
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


# ── Instance globale du gestionnaire ────────────
task_manager = TaskManager()
