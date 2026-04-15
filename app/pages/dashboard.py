"""
dashboard.py — Page principale.
Formulaire TRU Serial / IMEI, tableau des taches en temps reel,
modal pour afficher le resultat detaille,
modal de lookup (confirmation/selection device).
"""

import re
import os
import json
import logging
from datetime import datetime
from dash import html, dcc, callback, Input, Output, State, no_update, ctx, ALL

from app.tasks import task_manager
from app.crypto import get_tokens
from app.i18n import t
from app.report import generate_report_pdf
from app.api_client import lookup_devices_by_serial

logger = logging.getLogger(__name__)

# Regex IMEI : exactement 15 chiffres, commence par 8
IMEI_REGEX = re.compile(r"^8\d{14}$")


def layout(lang: str = "en"):
    """Retourne le layout de la page dashboard."""
    return html.Div(
        className="dashboard-container",
        children=[
            # ── Header ──────────────────────────────
            html.H1(t("dash.title", lang), className="dashboard-title"),
            # ── Toggle TRU / IMEI ───────────────────
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
            # ── Formulaire de saisie (card glass) ───
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
            # ── Tableau des taches ──────────────────
            html.Div(id="dash-task-table", className="task-table-container"),
            # ── Modal resultat detaille ─────────────
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
            # ── Modal lookup (confirmation/selection device) ──
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
            # ── Stores ───────────────────────────────
            dcc.Interval(id="dash-interval", interval=1000, n_intervals=0),
            dcc.Store(id="modal-task-id-store"),
            dcc.Store(id="report-status-store"),
            # Store pour les resultats du lookup (liste de devices)
            dcc.Store(id="lookup-devices-store"),
            # Store pour le TRU serial en cours de lookup
            dcc.Store(id="lookup-tru-store"),
            # Store pour l'IMEI selectionne dans le modal lookup
            dcc.Store(id="lookup-selected-imei-store"),
            # Store pour declencher le lancement apres selection
            dcc.Store(id="lookup-launch-store"),
        ],
    )


# ══════════════════════════════════════════════════
#  CALLBACKS
# ══════════════════════════════════════════════════

# ── Toggle mode TRU / IMEI ────────────────────────

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
    """Bascule entre mode TRU Serial et IMEI."""
    lang = lang or "en"
    triggered = ctx.triggered_id

    if triggered == "mode-imei-btn":
        return (
            "imei",
            "id-mode-btn",
            "id-mode-btn active",
            {"display": "block"},  # TRU visible (optionnel)
            {"display": "block"},  # IMEI visible
            t("dash.tru_placeholder", lang),
        )

    # Default: TRU mode
    return (
        "tru",
        "id-mode-btn active",
        "id-mode-btn",
        {"display": "block"},  # TRU visible (requis)
        {"display": "none"},   # IMEI masque
        t("dash.tru_required_placeholder", lang),
    )


# ── Validation input ─────────────────────────────

@callback(
    Output("dash-launch-btn", "disabled"),
    Output("dash-imei", "className"),
    Input("dash-imei", "value"),
    Input("dash-tru-serial", "value"),
    Input("id-mode-store", "data"),
)
def validate_input(imei_value, tru_value, mode):
    """Active/desactive le bouton selon le mode et la validite des champs."""
    if mode == "imei":
        if not imei_value:
            return True, "form-input"
        if not IMEI_REGEX.match(imei_value):
            return True, "form-input input-error"
        return False, "form-input"
    else:  # mode == "tru"
        if not tru_value or not tru_value.strip():
            return True, "form-input"
        return False, "form-input"


# ── Lancement du test ─────────────────────────────

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
    """Lance une tache de test ou effectue un lookup TRU."""
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

    # ── Mode IMEI : lancement direct ──
    if mode == "imei":
        if not imei:
            return (no_update,) * 9
        task_manager.create_task(imei, tru_serial or "", tokens)
        return "", "", "", *no_modal

    # ── Mode TRU : lookup puis modal ──
    if not tru_serial or not tru_serial.strip():
        return (no_update,) * 9

    tru_serial = tru_serial.strip()
    flespi_token = tokens.get("flespi_token", "")
    devices = lookup_devices_by_serial(tru_serial, flespi_token)

    if devices is None:
        # Erreur reseau
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
        # Aucun device trouve
        return (
            "",
            no_update,
            no_update,
            "modal-overlay visible",
            t("lookup.no_device", lang),
            html.P(t("lookup.no_device", lang), style={"textAlign": "center", "padding": "1rem"}),
            None,
            None,
            None,
        )

    # 1 ou N devices trouves → modal de confirmation/selection
    title = t("lookup.found_title", lang, count=len(devices))
    body = _build_lookup_modal_body(devices, lang, auto_select=(len(devices) == 1))

    # Stocker les devices et le TRU serial pour le callback de lancement
    devices_data = [{"ident": d["ident"], "name": d["name"], "connected": d["connected"]} for d in devices]

    # Pre-selectionner l'IMEI si 1 seul device
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
    """Construit le body du modal de lookup avec la liste des devices."""
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
            html.Div(
                className="lookup-device-list",
                children=device_buttons,
            ),
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


# ── Selection d'un device dans le modal lookup ────

@callback(
    Output("lookup-modal-body", "children", allow_duplicate=True),
    Output("lookup-selected-imei-store", "data"),
    Input({"type": "lookup-device-select", "index": ALL}, "n_clicks"),
    State("lookup-devices-store", "data"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def select_lookup_device(n_clicks_list, devices_data, lang):
    """Quand un IMEI est clique dans le modal, le selectionner (radio)."""
    lang = lang or "en"

    if not devices_data or not any(n_clicks_list):
        return no_update, no_update

    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return no_update, no_update

    selected_index = triggered["index"]
    selected_imei = devices_data[selected_index]["ident"]

    # Reconstruire le body avec le bon device selectionne
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
            html.Div(
                className="lookup-device-list",
                children=device_buttons,
            ),
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


# ── Lancement depuis le modal lookup ──────────────

@callback(
    Output("lookup-modal-overlay", "className", allow_duplicate=True),
    Output("lookup-launch-store", "data"),
    Input("lookup-launch-btn", "n_clicks"),
    State("lookup-selected-imei-store", "data"),
    State("lookup-tru-store", "data"),
    prevent_initial_call=True,
)
def launch_from_lookup(n_clicks, selected_imei, tru_serial):
    """Lance le test avec l'IMEI selectionne dans le modal lookup."""
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


# ── Fermeture du modal lookup ─────────────────────

@callback(
    Output("lookup-modal-overlay", "className", allow_duplicate=True),
    Input("lookup-modal-close-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_lookup_modal(n_clicks):
    """Ferme le modal de lookup."""
    if not n_clicks:
        return no_update
    return "modal-overlay hidden"


# ══════════════════════════════════════════════════
#  TABLE + RESULT MODAL (inchange)
# ══════════════════════════════════════════════════

@callback(
    Output("dash-task-table", "children"),
    Input("dash-interval", "n_intervals"),
    State("lang-store", "data"),
)
def update_task_table(n_intervals, lang):
    """Met a jour le tableau des taches toutes les secondes."""
    lang = lang or "en"
    
    # Nettoyer les tâches au premier appel (au démarrage de l'application)
    if n_intervals <= 1:
        logger.info(f"Nettoyage des tâches au démarrage (n_intervals={n_intervals})")
        task_manager.clear_tasks()
    
    tasks = task_manager.get_all_tasks()
    logger.info(f"Nombre de tâches après nettoyage: {len(tasks)}")

    if not tasks:
        return html.P(t("dash.no_tasks", lang), className="no-tasks")

    # Couleurs par statut pour le gradient de progression
    STATUS_COLORS = {
        "running": "76, 110, 245",
        "success": "81, 207, 102",
        "failed": "245, 159, 0",
        "error": "255, 107, 107",
        "unknown": "252, 196, 25",
    }

    # Header du tableau
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

    # Trier par date de creation (plus recent en haut)
    tasks.sort(key=lambda task: task.get("created_at", ""), reverse=True)

    for task in tasks:
        status_icon = _get_status_icon(task["status"])
        status_text = t(f"status.{task['status']}", lang)

        # Traduire l'etape courante (cle i18n → texte + step_extra pour Try X/Y)
        step_extra = task.get("step_extra") or {}
        step_display = t(task["current_step"], lang, **step_extra)

        # Si en attente : afficher le countdown traduit
        wait_msg = task.get("wait_message")
        if wait_msg and isinstance(wait_msg, dict):
            step_display = t(wait_msg["key"], lang, **{
                k: v for k, v in wait_msg.items() if k != "key"
            })

        # Background gradient = barre de progression integree
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

        # Colonne resultat
        result_cell = _build_result_cell(task, lang)

        row = html.Div(
            className=f"task-row status-row-{task['status']}",
            style=row_style,
            children=[
                html.Span(task["imei"], className="col-imei mono"),
                html.Span(task["tru_serial"], className="col-tru"),
                html.Span(step_display, className="col-step"),
                html.Span(
                    f"{status_icon} {status_text}", className="col-status"
                ),
                html.Div(result_cell, className="col-result"),
            ],
        )
        rows.append(row)

    return html.Div(rows, className="task-table")


def _get_status_icon(status: str) -> str:
    return {
        "running": "\u23f3",
        "success": "\u2705",
        "failed": "\u274c",
        "error": "\U0001F6D1",
        "unknown": "\u26a0",
    }.get(status, "")


def _build_result_cell(task: dict, lang: str):
    """Construit le contenu de la colonne Resultat."""
    if task["status"] == "running":
        return html.Span("\u2014", className="result-pending")

    if task["status"] in ("success", "failed", "error", "unknown"):
        return html.Button(
            t("table.view_btn", lang),
            id={"type": "view-result-btn", "index": task["task_id"]},
            className="btn-small",
            n_clicks=0,
        )

    return html.Span("\u2014")


def _build_result_modal(result: dict, lang: str):
    """Construit le contenu du modal pour un resultat RTC."""
    drift = result.get("drift", 0)
    drift_pct = (abs(drift) / 60000) * 100
    passed = drift_pct < 0.1

    # Timestamp du dernier drift
    drift_ts = result.get("last_drift_ts", 0)
    if drift_ts and drift_ts > 0:
        test_date = datetime.fromtimestamp(drift_ts).strftime("%m/%d/%Y %H:%M")
    else:
        test_date = "\u2014"

    badge_class = "badge-passed" if passed else "badge-failed"
    badge_text = t("result.passed", lang) if passed else t("result.failed", lang)

    return html.Div(
        className="result-details",
        children=[
            # Badge pass/fail
            html.Div(
                className="result-badge-row",
                children=[
                    html.Span(badge_text, className=f"result-badge {badge_class}"),
                ],
            ),
            # Drift brut
            html.Div(
                className="result-field",
                children=[
                    html.Span(t("result.drift_label", lang), className="result-key"),
                    html.Span(f"{drift} ms", className="result-value"),
                ],
            ),
            # Drift %
            html.Div(
                className="result-field",
                children=[
                    html.Span(t("result.drift_pct_label", lang), className="result-key"),
                    html.Span(f"{drift_pct:.4f}%", className="result-value"),
                ],
            ),
            # Duree du test
            html.Div(
                className="result-field",
                children=[
                    html.Span(t("result.test_duration_label", lang), className="result-key"),
                    html.Span("60 s", className="result-value"),
                ],
            ),
            # Seuil
            html.Div(
                className="result-field",
                children=[
                    html.Span(t("result.threshold_label", lang), className="result-key"),
                    html.Span("< 0.1%", className="result-value"),
                ],
            ),
            # Date du test
            html.Div(
                className="result-field",
                children=[
                    html.Span(t("result.test_date_label", lang), className="result-key"),
                    html.Span(test_date, className="result-value"),
                ],
            ),
            # Bouton Generate Report
            html.Div(
                className="report-btn-row",
                children=[
                    html.Button(
                        t("result.generate_report", lang),
                        id="generate-report-btn",
                        className="btn-primary",
                        n_clicks=0,
                        style={
                            "background": "#ffffff",
                            "color": "#000000",
                            "border": "1px solid #cccccc",
                            "boxShadow": "0 0 8px rgba(255, 255, 255, 0.15)",
                            "width": "auto",
                            "padding": "0.35rem 1rem",
                            "fontSize": "0.85rem",
                            "minWidth": "120px",
                        },
                    ),
                ],
            ),
        ],
    )


def _build_error_modal(task: dict, lang: str):
    """Construit le contenu du modal pour une erreur."""
    step_extra = task.get("step_extra") or {}
    step_text = t(task["current_step"], lang, **step_extra)
    error_key = task.get("error", "")
    error_extra = task.get("error_extra", {}) or {}
    error_text = t(error_key, lang, **error_extra) if error_key else "Error"

    return html.Div(
        className="result-details",
        children=[
            # Badge Failed
            html.Div(
                className="result-badge-row",
                children=[
                    html.Span(
                        t("result.failed", lang),
                        className="result-badge badge-failed",
                    ),
                ],
            ),
            # Etape
            html.Div(
                className="result-field",
                children=[
                    html.Span(t("table.step", lang), className="result-key"),
                    html.Span(step_text, className="result-value"),
                ],
            ),
            # Detail de l'erreur
            html.Div(
                className="result-field",
                children=[
                    html.Span(t("modal.error_detail", lang), className="result-key"),
                    html.Span(error_text, className="result-value result-error"),
                ],
            ),
        ],
    )


# ── Modal resultat : ouvrir / fermer ──────────────

@callback(
    Output("modal-overlay", "className"),
    Output("modal-title", "children"),
    Output("modal-body", "children"),
    Output("modal-task-id-store", "data"),
    Input({"type": "view-result-btn", "index": ALL}, "n_clicks"),
    Input("modal-close-btn", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def toggle_modal(view_clicks, close_clicks, lang):
    """Ouvre ou ferme le modal de resultat."""
    lang = lang or "en"

    # Ignore re-renders where no actual click happened
    if not any(tr.get("value") and tr["value"] > 0 for tr in ctx.triggered):
        return no_update, no_update, no_update, no_update

    triggered = ctx.triggered_id

    # Fermeture du modal
    if triggered == "modal-close-btn":
        return "modal-overlay hidden", "", "", None

    # Ouverture : identifier la tache
    if isinstance(triggered, dict) and triggered.get("type") == "view-result-btn":
        task_id = triggered["index"]
        task = task_manager.get_task(task_id)
        if not task:
            return "modal-overlay hidden", "", "", None

        title = t("modal.title", lang, imei=task["imei"])
        result = task.get("result")

        if task["status"] == "error":
            body = _build_error_modal(task, lang)
        elif task["status"] in ("success", "failed") and isinstance(result, dict):
            body = _build_result_modal(result, lang)
        else:
            body = html.Div(
                className="result-raw",
                children=[
                    html.P(t("modal.unexpected", lang)),
                    html.Pre(str(result)),
                ],
            )

        return "modal-overlay visible", title, body, task_id

    return no_update, no_update, no_update, no_update


# ── Generation rapport PDF ───────────────────────

REPORTS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "RTC_Reports")


@callback(
    Output("report-status-store", "data"),
    Input("generate-report-btn", "n_clicks"),
    State("modal-task-id-store", "data"),
    prevent_initial_call=True,
)
def generate_report(n_clicks, task_id):
    """Genere le PDF, le sauvegarde et l'ouvre."""
    if not n_clicks or not task_id:
        return no_update

    task = task_manager.get_task(task_id)
    if not task or task["status"] not in ("success", "failed"):
        return no_update

    pdf_bytes = generate_report_pdf(
        imei=task["imei"],
        tru_serial=task["tru_serial"],
        result=task["result"],
    )

    if not pdf_bytes:
        return no_update

    # Sauvegarder dans ~/Documents/RTC_Reports/
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = f"RTC_Report_{task['imei']}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)

    # Ouvrir avec le viewer PDF par defaut
    os.startfile(filepath)

    return {"saved": filepath}
