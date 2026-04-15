"""
dash_app.py — Instance Dash, layout principal, routing entre pages.
Le CSS est charge automatiquement depuis app/assets/style.css.
"""

import os
from dash import Dash, html, dcc, callback, Input, Output

# Import des pages au top-level pour enregistrer tous les @callback
from app.pages import dashboard


def create_app() -> Dash:
    """Cree et configure l'application Dash."""
    assets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="RCC App",
        assets_folder=assets_path,
    )

    app.layout = html.Div(
        children=[
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="lang-store", data="en", storage_type="local"),
            html.Div(id="page-content"),
        ]
    )

    # ── Routing ──────────────────────────────────
    @callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
        Input("lang-store", "data"),
    )
    def display_page(pathname, lang):
        return dashboard.layout(lang or "en")

    return app
