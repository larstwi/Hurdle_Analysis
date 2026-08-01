#!/usr/bin/env python3
"""xlsx- und PDF-Bytes fuer einen Athleten/eine Saison.

Bewusst ohne Streamlit-Import, damit diese Funktionen mit einfachem
`python3 -c "..."` getestet werden koennen, ohne einen App-Kontext zu brauchen.
"""

import io

from athletenblatt import baue as baue_xlsx
from pdf_export import baue_pdf


def xlsx_bytes(master, athlet, saison):
    """Erzeugt das Athletenblatt und gibt es als Bytes zurueck (kein Datei-Umweg)."""
    puffer = io.BytesIO()
    baue_xlsx(master, athlet, saison, puffer)
    puffer.seek(0)
    return puffer.read()


def pdf_bytes(master, athlet, saison):
    return baue_pdf(master, athlet, saison).read()
