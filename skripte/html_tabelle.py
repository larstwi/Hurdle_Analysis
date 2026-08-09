#!/usr/bin/env python3
"""HTML-Pendant zur PDF-/Excel-Rennliste, fuer die Streamlit-App.

Nutzt dieselbe Berechnungslogik wie pdf_export.py (segmente(), Zwischenzeit-
Klammern, 0-200/200-400/Diff), damit App, PDF und Excel nie auseinanderlaufen.
Rendert eine echte HTML-<table> mit rowspan statt Excel-Zellverschmelzung -
das macht den PB-Goldrahmen hier trivial und ohne die Merge-Eigenheiten, mit
denen der Excel-Export zu kaempfen hatte.
"""

import pandas as pd

from auswertung import segmente, kuerzel_runde

TINTE = '#1F3348'
KOPF_HELL = '#DCE3EA'
GRAU = '#6B7A8A'
GOLD = '#B8860B'
GOLD_HELL = '#FBF0CE'
SCHRITTZEILE = '#EDF1F5'
RAND = '#B8C4D0'
VERGLEICH_TEXT = '#5A6B7C'

SPALTEN_RENNEN = ['Datum', 'Ort', 'Rd', 'Bahn', 'Rang']
SPALTEN_ERGEBNIS = ['Zeit', '0–200', '200–400', 'Diff']
SPALTEN_ABSCHNITT = ['Start–H1'] + [f'H{i}–H{i+1}' for i in range(1, 10)] + ['H10–Ziel']

_CSS = f"""
<style>
.rtab-wrap {{ overflow-x: auto; margin-bottom: 0.5rem; background: #ffffff;
              border-radius: 4px; padding: 1px; }}
table.rtab {{ border-collapse: collapse; width: 100%; font-family: Arial, Helvetica, sans-serif;
              font-size: 12.5px; color: #1A2430; background: #ffffff; }}
table.rtab th, table.rtab td {{ border: 1px solid {RAND}; padding: 4px 7px; text-align: center;
                                 white-space: nowrap; background: #ffffff; color: #1A2430; }}
table.rtab td.left {{ text-align: left; }}
table.rtab tr.grp th {{ background: {TINTE}; color: white; font-weight: 700; font-size: 12px;
                         padding: 5px 7px; }}
table.rtab tr.hdr th {{ background: {KOPF_HELL}; color: {TINTE}; font-weight: 700; }}
table.rtab td.zeit {{ font-weight: 700; }}
table.rtab tr.r2 td {{ background: {SCHRITTZEILE}; color: {VERGLEICH_TEXT}; font-size: 11.5px; }}
table.rtab tr.vgl td {{ font-style: italic; color: {VERGLEICH_TEXT}; }}
table.rtab tr.vgl.r2 td {{ font-style: italic; }}
table.rtab tr.pb.r1 td {{ border-top: 2px solid {GOLD}; }}
table.rtab tr.pb.r2 td {{ border-bottom: 2px solid {GOLD}; }}
table.rtab tr.pb.r1 td:nth-child(-n+9) {{ border-bottom: 2px solid {GOLD}; }}
table.rtab tr.pb.r1 td:first-child {{ border-left: 2px solid {GOLD}; }}
table.rtab tr.pb.r1 td:last-child, table.rtab tr.pb.r2 td:last-child {{
    border-right: 2px solid {GOLD}; }}
table.rtab tr.pb.r1 td:nth-child(-n+9) {{ background: {GOLD_HELL}; }}
</style>
"""


def _fmt(v, nachkomma=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    if isinstance(v, str):
        return v
    return f'{v:.{nachkomma}f}'


def _h200_h400_diff(row):
    h5, h6, zeit = row.get('h5'), row.get('h6'), row.get('zeit')
    if pd.isna(h5) or pd.isna(h6):
        return None, None, None
    m200 = h5 + (h6 - h5) * 14 / 35
    if pd.isna(zeit):
        return round(m200, 2), None, None
    m400 = zeit - m200
    return round(m200, 2), round(m400, 2), round(m400 - m200, 2)


def _segment_zellen(row):
    """Liste von (Zeit-Text, Schritt-Text) je Abschnitt - 'Segment (Zwischenzeit)'
    wie im PDF/Excel, Start-H1 ohne Klammer."""
    seg, schritte = segmente(row)

    def f(v):
        return None if v is None or (isinstance(v, float) and pd.isna(v)) else float(v)

    h = [f(row.get(f'h{i}')) for i in range(1, 11)]
    zeit_num = f(row.get('zeit'))
    zwischen = [h[0]] + h[1:10] + [zeit_num]

    zellen = []
    for i in range(len(seg)):
        if seg[i] is None:
            zeit_txt = ''
        elif i == 0:
            zeit_txt = _fmt(seg[i])
        else:
            zw = _fmt(zwischen[i])
            zeit_txt = f'{_fmt(seg[i])} ({zw})' if zw != '' else _fmt(seg[i])
        # schritte hat nur 10 Eintraege (kein Schrittwert H10->Ziel), seg 11 -
        # die letzte Abschnittsspalte bleibt bei den Schritten daher leer.
        schritt_txt = _fmt(schritte[i], 0) if i < len(schritte) and schritte[i] is not None else ''
        zellen.append((zeit_txt, schritt_txt))
    return zellen


def _kopfzeilen():
    html = ['<tr class="grp">']
    html.append(f'<th colspan="{len(SPALTEN_RENNEN)}">RENNEN</th>')
    html.append(f'<th colspan="{len(SPALTEN_ERGEBNIS)}">ERGEBNIS</th>')
    html.append(f'<th colspan="{len(SPALTEN_ABSCHNITT)}">ABSCHNITTE &middot; Sekunden '
                '(Zwischenzeit) &middot; unten Schritte</th>')
    html.append('</tr><tr class="hdr">')
    for t in SPALTEN_RENNEN + SPALTEN_ERGEBNIS + SPALTEN_ABSCHNITT:
        html.append(f'<th>{t}</th>')
    html.append('</tr>')
    return ''.join(html)


def _rennzeilen_html(rennen, pb_id, vgl=False):
    html = []
    for _, row in rennen.iterrows():
        ist_pb = pb_id is not None and row['race_id'] == pb_id
        m200, m400, diff = _h200_h400_diff(row)
        datum = (pd.to_datetime(row['datum']).strftime('%d.%m.%Y')
                 if pd.notna(row.get('datum')) else '')
        ort = row.get('ort') or ''
        rd = kuerzel_runde(row.get('runde'), row.get('lauf'))
        bahn = _fmt(row.get('bahn'), 0)
        rang = _fmt(row.get('rang'), 0)
        zeit_txt = str(row['status']) if row['status'] != 'OK' else _fmt(row.get('zeit'))
        diff_txt = (('+' if diff and diff > 0 else '') + _fmt(diff)) if diff is not None else ''
        segmente_zellen = _segment_zellen(row)

        klassen = ('vgl ' if vgl else '') + ('pb ' if ist_pb else '')

        html.append(f'<tr class="{klassen}r1">')
        linksbuendig = {0, 1}   # Datum, Ort
        for i, wert in enumerate((datum, ort, rd, bahn, rang)):
            cls = ' class="left"' if i in linksbuendig else ''
            html.append(f'<td rowspan="2"{cls}>{wert}</td>')
        html.append(f'<td rowspan="2" class="zeit">{zeit_txt}</td>')
        html.append(f'<td rowspan="2">{_fmt(m200)}</td>')
        html.append(f'<td rowspan="2">{_fmt(m400)}</td>')
        html.append(f'<td rowspan="2">{diff_txt}</td>')
        for zeit_z, _ in segmente_zellen:
            html.append(f'<td>{zeit_z}</td>')
        html.append('</tr>')

        html.append(f'<tr class="{klassen}r2">')
        for _, schritt_z in segmente_zellen:
            html.append(f'<td>{schritt_z}</td>')
        html.append('</tr>')
    return ''.join(html)


def rennen_tabelle_html(rennen, pb_id=None, vgl=False):
    """Vollstaendige HTML-Tabelle (mit <style>) fuer eine Rennliste - direkt per
    st.markdown(..., unsafe_allow_html=True) einbindbar."""
    if rennen.empty:
        return ''
    body = _rennzeilen_html(rennen, pb_id, vgl=vgl)
    return (f'{_CSS}<div class="rtab-wrap"><table class="rtab">'
            f'{_kopfzeilen()}{body}</table></div>')
