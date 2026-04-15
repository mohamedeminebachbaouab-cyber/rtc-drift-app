"""
report.py — Generation de PDF de rapport RTC a partir du template HTML.
Utilise xhtml2pdf pour la conversion HTML -> PDF.
"""

import io
import os
import base64
import logging
from datetime import datetime

from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

# Charger le logo en base64 au demarrage (fonctionne offline + PyInstaller)
_LOGO_B64 = ""
_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "carrier_logo.png")
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

.logo {
  height: 12mm;
  width: auto;
  display: block;
  margin-bottom: 6mm;
}

h1 {
  font-size: 18pt;
  margin: 0 0 6mm 0;
  font-weight: 700;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table td {
  padding: 3mm 4mm;
  border-bottom: 1px solid #ddd;
  font-size: 11pt;
}

.label {
  font-weight: bold;
  width: 45%;
}

.result-passed {
  font-weight: bold;
  color: #1b5e20;
}

.result-failed {
  font-weight: bold;
  color: #b71c1c;
}

.footer {
  margin-top: 15mm;
  font-size: 9pt;
  color: #777;
  text-align: right;
}
</style>
</head>

<body>

<div class="a4-sheet">

  <img class="logo"
       src="%%LOGO_SRC%%"
       alt="Carrier Logo">

  <h1>RTC Clock Verification</h1>

  <table class="table">
    <tr>
      <td class="label">Device</td>
      <td>%%IMEI%%</td>
    </tr>
    <tr>
      <td class="label">TRU Serial</td>
      <td>%%TRU_SERIAL%%</td>
    </tr>
    <tr>
      <td class="label">Test executed on</td>
      <td>%%TEST_DATE%%</td>
    </tr>
    <tr>
      <td class="label">Maximum drift</td>
      <td>%%DRIFT_MS%% ms</td>
    </tr>
    <tr>
      <td class="label">Drift test duration</td>
      <td>60 s</td>
    </tr>
    <tr>
      <td class="label">Drift</td>
      <td>%%DRIFT_PCT%% %</td>
    </tr>
    <tr>
      <td class="label">Result</td>
      <td class="%%RESULT_CLASS%%">%%RESULT_TEXT%%</td>
    </tr>
  </table>

  <div class="footer">
    Official Verification Report
  </div>

</div>

</body>
</html>
"""


def generate_report_pdf(
    imei: str,
    tru_serial: str,
    result: dict,
) -> bytes | None:
    """
    Genere un PDF de rapport RTC a partir des donnees de la tache.
    Retourne les bytes du PDF, ou None en cas d'erreur.
    """
    drift = result.get("drift", 0)
    drift_pct = (abs(drift) / 60000) * 100
    passed = drift_pct < 0.1

    drift_ts = result.get("last_drift_ts", 0)
    if drift_ts and drift_ts > 0:
        test_date = datetime.fromtimestamp(drift_ts).strftime("%m/%d/%Y %H:%M")
    else:
        test_date = datetime.now().strftime("%m/%d/%Y %H:%M")

    result_text = "Passed" if passed else "Failed"
    result_class = "result-passed" if passed else "result-failed"

    logo_src = f"data:image/png;base64,{_LOGO_B64}" if _LOGO_B64 else ""

    html = REPORT_TEMPLATE
    html = html.replace("%%LOGO_SRC%%", logo_src)
    html = html.replace("%%IMEI%%", imei)
    html = html.replace("%%TRU_SERIAL%%", tru_serial)
    html = html.replace("%%TEST_DATE%%", test_date)
    html = html.replace("%%DRIFT_MS%%", str(drift))
    html = html.replace("%%DRIFT_PCT%%", f"{drift_pct:.4f}")
    html = html.replace("%%RESULT_TEXT%%", result_text)
    html = html.replace("%%RESULT_CLASS%%", result_class)

    try:
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)

        if pisa_status.err:
            logger.error(f"Erreur xhtml2pdf : {pisa_status.err}")
            return None

        pdf_buffer.seek(0)
        return pdf_buffer.read()

    except Exception as e:
        logger.exception(f"Erreur generation PDF : {e}")
        return None
