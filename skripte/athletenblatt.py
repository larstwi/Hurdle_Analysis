#!/usr/bin/env python3
"""Personalisiertes Auswertungsblatt fuer einen 400-m-Huerden-Athleten.

Aufbau pro Rennen: zwei Zeilen uebereinander.
  obere Zeile  - Abschnittszeiten in Sekunden
  untere Zeile - Schrittzahl im selben Abschnitt, exakt darunter

Farben werden direkt auf die Zellen geschrieben (nicht als bedingte
Formatierung), damit sie auch in Numbers und in Vorschauen erhalten bleiben.
Die Zahlen selbst bleiben Formeln auf das Blatt "Rohdaten".
"""

import sys
import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.series import SeriesLabel
from openpyxl.chart.data_source import StrRef

from master_io import load_master
from auswertung import select_season, kuerzel_runde
from xlsx_cache import injiziere_cache_werte

ARIAL = 'Arial'
TINTE, GRAU = '1F3348', '6B7A8A'
RAND = 'B8C4D0'

# Schrittzeile wird durchgehend leicht grau hinterlegt, damit sie sich
# klar von der weissen Zeitzeile darueber abhebt
SCHRITTZEILE = 'EDF1F5'
# Persoenliche Bestzeit bekommt einen goldenen Rahmen
GOLD = 'B8860B'
GOLD_HELL = 'FBF0CE'

# Ein Abschnitt, der deutlich schneller ist als der vorangehende, widerspricht
# dem Ermuedungsverlauf und deutet auf einen Tippfehler im Touchdown hin.
duenn = Side(style='thin', color=RAND)
gold = Side(style='medium', color=GOLD)
RAHMEN = Border(left=duenn, right=duenn, top=duenn, bottom=duenn)
OBEN = Border(left=duenn, right=duenn, top=duenn)
UNTEN = Border(left=duenn, right=duenn, bottom=duenn)

KOPF_RENNEN = ['Datum', 'Ort', 'Rd', 'Bahn', 'Rang']
KOPF_ERGEBNIS = ['Zeit', '0–200', '200–400', 'Diff']
KOPF_SEGMENT = ['Start–H1'] + [f'H{i}–H{i+1}' for i in range(1, 10)] + ['H10–Ziel']

C_ZEIT, C_H200, C_H400, C_DIFF = 6, 7, 8, 9
C_SEG0 = 10                      # Start–H1
C_SEG35_0, C_SEG35_1 = 11, 19    # die neun 35-m-Abschnitte
C_SEGZ = 20                      # H10–Ziel
BREIT = C_SEGZ

BREITEN = [11, 17, 5, 6, 6, 9, 8, 9, 8, 10] + [13] * 9 + [14]

# Spalten auf "Rohdaten"
R_DATUM, R_ORT, R_RUNDE, R_LAUF, R_BAHN, R_RANG, R_ZEIT, R_STATUS = 2, 3, 4, 5, 6, 7, 8, 9
R_H1, R_H5, R_H6, R_H10, R_S0 = 10, 14, 15, 19, 20
R_LABEL, R_KURZ = 30, 31


def rd(col, zeile):
    return f'Rohdaten!{L(col)}{zeile}'


def kopfzelle(ws, zelle, text, groesse=11, fett=True, vordergrund='FFFFFF',
              fuellung=TINTE, ausrichtung='center'):
    c = ws[zelle]
    c.value = text
    c.font = Font(name=ARIAL, size=groesse, bold=fett, color=vordergrund)
    if fuellung:
        c.fill = PatternFill('solid', fgColor=fuellung)
    c.alignment = Alignment(horizontal=ausrichtung, vertical='center', wrap_text=True)
    return c


def schreibe_rohdaten(ws, df):
    import datetime as _dt
    kopf = (['race_id', 'datum', 'ort', 'runde', 'lauf', 'bahn', 'rang', 'zeit', 'status']
            + [f'h{i}' for i in range(1, 11)]
            + ['s_start'] + [f's{i}_{i+1}' for i in range(1, 10)])
    for j, h in enumerate(kopf, 1):
        kopfzelle(ws, f'{L(j)}1', h, groesse=9)
    for i, (_, r) in enumerate(df.iterrows(), start=2):
        for j, h in enumerate(kopf, 1):
            v = r[h]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = ''
            if h == 'datum' and v:
                v = _dt.date.fromisoformat(str(v))
            c = ws.cell(i, j, v)
            c.font = Font(name=ARIAL, size=9)
            if h == 'datum':
                c.number_format = 'DD.MM.YYYY'
    kopfzelle(ws, f'{L(R_KURZ)}1', 'kurz', groesse=9)
    for i, (_, r) in enumerate(df.iterrows(), start=2):
        c = ws.cell(i, R_KURZ, kuerzel_runde(r['runde'], r['lauf']))
        c.font = Font(name=ARIAL, size=9)
    ws.column_dimensions[L(R_KURZ)].width = 7
    ws.freeze_panes = 'B2'
    for j, b in enumerate([22, 11, 13, 17, 5, 5, 5, 7, 7] + [7] * 19, 1):
        ws.column_dimensions[L(j)].width = b
    ws.sheet_view.showGridLines = False


def werte(r):
    """Abschnittszeiten und Schrittzahlen als Zahlen, fuer die Einfaerbung."""
    h = [r.get(f'h{i}') for i in range(1, 11)]
    h = [None if (v is None or v == '' or pd.isna(v)) else float(v) for v in h]
    z = r.get('zeit')
    z = None if (z is None or z == '' or pd.isna(z)) else float(z)

    seg = [h[0]]
    for i in range(9):
        seg.append(None if h[i] is None or h[i + 1] is None else round(h[i + 1] - h[i], 3))
    seg.append(None if h[9] is None or z is None else round(z - h[9], 3))

    s = [r.get('s_start')] + [r.get(f's{i}_{i+1}') for i in range(1, 10)]
    s = [None if (v is None or v == '' or pd.isna(v)) else int(v) for v in s]
    return seg, s


def exceldatum(d):
    """Python-Datum -> Excel-Seriennummer (Tage seit 1899-12-30, Excels Epoche)."""
    import datetime
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    return (d - datetime.date(1899, 12, 30)).days


def rennblock(ws, blattname, oben, quelle, daten, cache, blass=False):
    """Schreibt ein Rennen als zwei Zeilen. Gibt die naechste freie Zeile zurueck.

    cache sammelt (blattname, zellref, wert, ist_text) fuer jede Formel -
    wird am Ende in injiziere_cache_werte() genutzt, damit auch Programme
    mit schwacher Formel-Unterstuetzung (z.B. Apple Numbers) sofort die
    richtigen Werte zeigen, statt der leeren Formel-Zwischenspeicher, die
    openpyxl an sich hinterlaesst.
    """
    q, unten = quelle, oben + 1
    seg, schritte = werte(daten)
    ton = '5A6B7C' if blass else '1A2430'
    leer = lambda ref: f'IF({ref}="","",{ref})'

    def num(v):
        return None if (v is None or v == '' or (isinstance(v, float) and pd.isna(v))) else float(v)

    def merke(row, col, wert, ist_text=False):
        cache.append((blattname, f'{L(col)}{row}', wert, ist_text))

    h = [num(daten.get(f'h{i}')) for i in range(1, 11)]
    zeit_num = num(daten.get('zeit'))
    status = daten.get('status') or 'OK'
    kurz_txt = kuerzel_runde(daten.get('runde'), daten.get('lauf'))
    datum_txt = daten.get('datum')

    ws.cell(oben, 1, f'={leer(rd(R_DATUM, q))}')
    if datum_txt:
        merke(oben, 1, exceldatum(datum_txt))
    ws.cell(oben, 2, f'={leer(rd(R_ORT, q))}')
    if daten.get('ort'):
        merke(oben, 2, daten.get('ort'), True)
    ws.cell(oben, 3, f'={leer(rd(R_KURZ, q))}')
    if kurz_txt:
        merke(oben, 3, kurz_txt, True)
    ws.cell(oben, 4, f'={leer(rd(R_BAHN, q))}')
    if daten.get('bahn') not in (None, ''):
        merke(oben, 4, num(daten.get('bahn')))
    ws.cell(oben, 5, f'={leer(rd(R_RANG, q))}')
    if daten.get('rang') not in (None, ''):
        merke(oben, 5, num(daten.get('rang')))

    ws.cell(oben, C_ZEIT, f'=IF({rd(R_STATUS, q)}<>"OK",{rd(R_STATUS, q)},{rd(R_ZEIT, q)})')
    if status != 'OK':
        merke(oben, C_ZEIT, status, True)
    elif zeit_num is not None:
        merke(oben, C_ZEIT, zeit_num)

    h5, h6 = rd(R_H5, q), rd(R_H6, q)
    m200 = None if h[4] is None or h[5] is None else h[4] + (h[5] - h[4]) * 14 / 35
    ws.cell(oben, C_H200, f'=IF(OR({h5}="",{h6}=""),"",{h5}+({h6}-{h5})*14/35)')
    if m200 is not None:
        merke(oben, C_H200, round(m200, 4))

    m400 = None if m200 is None or zeit_num is None else zeit_num - m200
    ws.cell(oben, C_H400, f'=IF(OR({L(C_H200)}{oben}="",{rd(R_ZEIT, q)}=""),"",'
                          f'{rd(R_ZEIT, q)}-{L(C_H200)}{oben})')
    if m400 is not None:
        merke(oben, C_H400, round(m400, 4))

    diff = None if m200 is None or m400 is None else m400 - m200
    ws.cell(oben, C_DIFF, f'=IF(OR({L(C_H200)}{oben}="",{L(C_H400)}{oben}=""),"",'
                          f'{L(C_H400)}{oben}-{L(C_H200)}{oben})')
    if diff is not None:
        merke(oben, C_DIFF, round(diff, 4))

    for j in range(1, C_DIFF + 1):
        ws.merge_cells(start_row=oben, start_column=j, end_row=unten, end_column=j)

    ws.cell(oben, C_SEG0, f'=IF({rd(R_H1, q)}="","",{rd(R_H1, q)})')
    if h[0] is not None:
        merke(oben, C_SEG0, h[0])

    # Diese Zellen sind reine Anzeige (Segmentzeit + Zwischenzeit als Text
    # "0.55 (6.88)") und werden bewusst NICHT als Formel geschrieben: das
    # noetige TEXT()-plus-Verkettungs-Konstrukt wird von Apple Numbers und
    # der iOS-Vorschau nicht zuverlaessig ausgewertet und faellt dort auf 0
    # zurueck - selbst mit injiziertem Formel-Cache (siehe xlsx_cache.py,
    # das fuer einfache Passthrough-Formeln wie Start-H1 oder die
    # Schrittzahlen einwandfrei funktioniert, aber nicht fuer verschachtelte
    # TEXT()-Formeln). Der Wert wird daher direkt und endgueltig als Text
    # geschrieben; er bleibt dadurch nicht mit "Rohdaten" verknuepft, ist
    # dafuer aber in jeder Anwendung korrekt sichtbar.
    for i in range(9):
        if h[i] is not None and h[i + 1] is not None:
            ws.cell(oben, C_SEG35_0 + i, f'{h[i+1]-h[i]:.2f} ({h[i+1]:.2f})')
        else:
            ws.cell(oben, C_SEG35_0 + i, '')

    if h[9] is not None and zeit_num is not None:
        ws.cell(oben, C_SEGZ, f'{zeit_num-h[9]:.2f} ({zeit_num:.2f})')
    else:
        ws.cell(oben, C_SEGZ, '')

    s_namen = ['s_start'] + [f's{k}_{k+1}' for k in range(1, 10)]
    for i in range(10):
        ws.cell(unten, C_SEG0 + i, f'={leer(rd(R_S0 + i, q))}')
        sv = daten.get(s_namen[i])
        if sv not in (None, '') and not (isinstance(sv, float) and pd.isna(sv)):
            merke(unten, C_SEG0 + i, int(float(sv)))

    for j in range(1, BREIT + 1):
        c = ws.cell(oben, j)
        c.font = Font(name=ARIAL, size=10, color=ton, bold=(j == C_ZEIT), italic=blass)
        c.border = OBEN if j >= C_SEG0 else RAHMEN
        c.alignment = Alignment(horizontal='left' if j in (2, 3) else 'center',
                                vertical='center')
        if j == 1:
            c.number_format = 'DD.MM.YYYY'
        elif j == C_DIFF:
            c.number_format = '+0.00;−0.00;0.00'
        elif j == C_ZEIT or j in (C_H200, C_H400) or j == C_SEG0:
            c.number_format = '0.00'
        elif j > C_SEG0:
            c.number_format = '@'   # Text: "Segment (Zwischenzeit)"

    for j in range(1, C_DIFF + 1):
        ws.cell(unten, j).border = UNTEN

    for j in range(C_SEG0, BREIT + 1):
        c = ws.cell(unten, j)
        c.font = Font(name=ARIAL, size=9, color='3D4B59', italic=blass)
        c.border = UNTEN
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.number_format = '0'
        c.fill = PatternFill('solid', fgColor=SCHRITTZEILE)

    ws.row_dimensions[oben].height = 17
    ws.row_dimensions[unten].height = 13
    return unten + 1


def markiere_bestzeit(ws, oben, unten, breit):
    """Legt einen goldenen Rahmen um den Rennblock der persoenlichen Bestzeit."""
    for j in range(1, breit + 1):
        for r, kante in ((oben, 'top'), (unten, 'bottom')):
            c = ws.cell(r, j)
            alt = c.border
            c.border = Border(
                left=gold if j == 1 else alt.left,
                right=gold if j == breit else alt.right,
                top=gold if kante == 'top' else alt.top,
                bottom=gold if kante == 'bottom' else alt.bottom)
    kopf = ws.cell(oben, 1)
    kopf.fill = PatternFill('solid', fgColor=GOLD_HELL)
    kopf.comment = Comment('Persönliche Bestzeit', 'Auswertung')


def baue(master, athlet, saison, ziel, vergleiche=4):
    auswahl = select_season(master, athlet, saison, vergleiche)
    lauf, vgl = auswahl['lauf'], auswahl['vgl']
    sb, pb, pb_jahr, pb_id = auswahl['sb'], auswahl['pb'], auswahl['pb_jahr'], auswahl['pb_id']

    reihenfolge = pd.concat([lauf, vgl])
    idx = {rid: i + 2 for i, rid in enumerate(reihenfolge['race_id'])}

    wb = Workbook()
    ws = wb.active
    ws.title = 'Saison'
    roh = wb.create_sheet('Rohdaten')
    schreibe_rohdaten(roh, reihenfolge)

    for j, b in enumerate(BREITEN, 1):
        ws.column_dimensions[L(j)].width = b

    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=BREIT)
    kopfzelle(ws, 'A1', f'{str(athlet).upper()}   ·   400 M HÜRDEN   ·   SAISON {saison}',
              groesse=17, ausrichtung='left')
    ws.row_dimensions[1].height = 20
    ws.row_dimensions[2].height = 18

    kpi = [('Saisonbestzeit', f'{sb:.2f} s' if pd.notna(sb) else '—'),
           ('Persönliche Bestzeit', f'{pb:.2f} s' if pd.notna(pb) else '—'),
           ('Jahr', str(pb_jahr) if pb_jahr else '—'),
           ('Rennen in der Saison', str(len(lauf))),
           ('Beendet', str(int((lauf['status'] == 'OK').sum())))]
    sp = 1
    for titel, wert in kpi:
        ws.merge_cells(start_row=3, start_column=sp, end_row=3, end_column=sp + 2)
        ws.merge_cells(start_row=4, start_column=sp, end_row=4, end_column=sp + 2)
        kopfzelle(ws, f'{L(sp)}3', titel, groesse=8, fett=False,
                  vordergrund=GRAU, fuellung=None, ausrichtung='left')
        kopfzelle(ws, f'{L(sp)}4', wert, groesse=14, vordergrund=TINTE,
                  fuellung=None, ausrichtung='left')
        sp += 3
    ws.row_dimensions[4].height = 20

    ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=BREIT)
    kopfzelle(ws, 'A5',
              'Je Rennen zwei Zeilen: oben die Abschnittszeit mit Zwischenzeit seit Start in '
              'Klammern, darunter die Schrittzahl im gleichen Abschnitt.   '
              'Goldener Rahmen = persönliche Bestzeit.',
              groesse=8, fett=False, vordergrund=GRAU, fuellung=None, ausrichtung='left')
    ws.row_dimensions[5].height = 14

    for a, b, t in [(1, 5, 'RENNEN'), (C_ZEIT, C_DIFF, 'ERGEBNIS'),
                    (C_SEG0, C_SEGZ, 'ABSCHNITTE   ·   Sekunden (Zwischenzeit)   ·   unten Schritte')]:
        ws.merge_cells(start_row=7, start_column=a, end_row=7, end_column=b)
        kopfzelle(ws, f'{L(a)}7', t, groesse=9)
    for j, t in enumerate(KOPF_RENNEN + KOPF_ERGEBNIS + KOPF_SEGMENT, 1):
        c = kopfzelle(ws, f'{L(j)}8', t, groesse=9, fuellung='DCE3EA', vordergrund=TINTE)
        c.border = RAHMEN
    ws.row_dimensions[7].height = 16
    ws.row_dimensions[8].height = 24

    z = 9
    saison_zeilen, block_von = [], {}
    formel_cache = []
    for _, r in lauf.iterrows():
        saison_zeilen.append(z)
        block_von[r['race_id']] = z
        z = rennblock(ws, 'Saison', z, idx[r['race_id']], r, formel_cache)

    if not vgl.empty:
        z += 1
        ws.merge_cells(start_row=z, start_column=1, end_row=z, end_column=BREIT)
        kopfzelle(ws, f'A{z}', 'VERGLEICH FRÜHERE JAHRE   ·   bestes Rennen je Saison, neuestes zuerst',
                  groesse=9, fuellung=GRAU, ausrichtung='left')
        z += 1
        for _, r in vgl.iterrows():
            block_von[r['race_id']] = z
            z = rennblock(ws, 'Saison', z, idx[r['race_id']], r, formel_cache, blass=True)
    letzte = z - 1

    if pb_id and pb_id in block_von:
        o = block_von[pb_id]
        markiere_bestzeit(ws, o, o + 1, C_DIFF)

    # ---------- Bezeichner fuer die Diagrammlegenden ----------
    # Auch hier bewusst als fertiger Text statt TEXT()-Verkettungsformel
    # geschrieben (gleicher Grund wie bei den Abschnittszellen oben) -
    # sonst zeigen die Diagrammlegenden in Numbers/Vorschau nichts an.
    kopfzelle(roh, f'{L(R_LABEL)}1', 'legende', groesse=9)
    roh.column_dimensions[L(R_LABEL)].width = 24
    label_von = {}
    for _, r in reihenfolge.iterrows():
        q = idx[r['race_id']]
        kurz = kuerzel_runde(r['runde'], r['lauf'])
        datum_txt = pd.to_datetime(r['datum']).strftime('%d.%m.') if r.get('datum') else ''
        label = f"{datum_txt} {r['ort']}" + (f' {kurz}' if kurz else ' ')
        label_von[r['race_id']] = label
        c = roh.cell(q, R_LABEL, label)
        c.font = Font(name=ARIAL, size=9)

    # ---------- Rechenblatt fuer die Kurven ----------
    # Blatt fuer die Diagramme, Rechnung liegt auf einem eigenen Blatt dahinter
    gr = wb.create_sheet('Grafiken')
    gr.sheet_view.showGridLines = False
    kv = wb.create_sheet('Berechnung')
    kv.sheet_view.showGridLines = False
    kv.column_dimensions['A'].width = 26
    for j in range(2, 14):
        kv.column_dimensions[L(j)].width = 9
    KOPFRAUM = 1

    def beschriftung(zeile, spalten, texte):
        for j, t in enumerate(texte, spalten):
            kopfzelle(kv, f'{L(j)}{zeile}', t, groesse=9)

    # --- Block 1: kumulierter Rueckstand zum Referenzrennen ---
    ref = auswahl['ref']
    ref_name = ''
    if ref is not None:
        ref_name = (f"{pd.to_datetime(ref['datum']).strftime('%d.%m.%y')} {ref['ort']}"
                    f" — {float(ref['zeit']):.2f} s")
    kopfzelle(kv, f'A{KOPFRAUM}', f'Kumulierter Rückstand zur Referenz ({ref_name})',
              groesse=10, ausrichtung='left')
    kv.merge_cells(f'A{KOPFRAUM}:L{KOPFRAUM}')
    kat1 = KOPFRAUM + 1
    beschriftung(kat1, 2, [f'H{i}' for i in range(1, 11)] + ['Ziel'])
    kopfzelle(kv, f'A{kat1}', 'Rennen', groesse=9, ausrichtung='left')

    z1 = kat1 + 1
    gap_zeilen = []
    if ref is not None:
        rq = idx[ref['race_id']]
        for _, r in lauf.iterrows():
            q = idx[r['race_id']]
            kv.cell(z1, 1, f'={rd(R_LABEL, q)}').font = Font(name=ARIAL, size=9)
            for i in range(10):
                a, b = rd(R_H1 + i, q), rd(R_H1 + i, rq)
                kv.cell(z1, 2 + i, f'=IF(OR({a}="",{b}=""),NA(),{a}-{b})')
            za, zb = rd(R_ZEIT, q), rd(R_ZEIT, rq)
            kv.cell(z1, 12, f'=IF(OR({za}="",{zb}=""),NA(),{za}-{zb})')
            for j in range(2, 13):
                kv.cell(z1, j).number_format = '+0.00;−0.00;0.00'
                kv.cell(z1, j).font = Font(name=ARIAL, size=9)
            gap_zeilen.append(z1)
            z1 += 1

    # --- Block 2: Ermuedungsprofil ---
    z2 = z1 + 2
    kopfzelle(kv, f'A{z2}', 'Ermüdungsprofil — Abschnitt minus schnellster Abschnitt '
                            'desselben Rennens (Sekunden)', groesse=10, ausrichtung='left')
    kv.merge_cells(f'A{z2}:L{z2}')
    z2 += 1
    beschriftung(z2, 2, [f'H{i}–H{i+1}' for i in range(1, 10)])
    kopfzelle(kv, f'A{z2}', 'Rennen', groesse=9, ausrichtung='left')
    kopf2 = z2
    z2 += 1

    # Hilfsspalten N..V: die neun Abschnitte je Rennen
    HILF = 14
    kopfzelle(kv, f'{L(HILF)}{kopf2}', 'Abschnitte (Hilfsspalten)', groesse=8)
    kv.merge_cells(start_row=kopf2, start_column=HILF, end_row=kopf2, end_column=HILF + 8)

    prof_zeilen = []
    for _, r in reihenfolge.iterrows():
        q = idx[r['race_id']]
        kv.cell(z2, 1, f'={rd(R_LABEL, q)}').font = Font(name=ARIAL, size=9)
        for i in range(9):
            a, b = rd(R_H1 + i, q), rd(R_H1 + i + 1, q)
            kv.cell(z2, HILF + i, f'=IF(OR({a}="",{b}=""),"",{b}-{a})')
            kv.cell(z2, HILF + i).font = Font(name=ARIAL, size=8, color=GRAU)
        bereich = f'{L(HILF)}{z2}:{L(HILF + 8)}{z2}'
        for i in range(9):
            zelle = f'{L(HILF + i)}{z2}'
            kv.cell(z2, 2 + i,
                    f'=IF({zelle}="",NA(),{zelle}-MIN({bereich}))')
            kv.cell(z2, 2 + i).number_format = '0.00'
            kv.cell(z2, 2 + i).font = Font(name=ARIAL, size=9)
        prof_zeilen.append((z2, r['race_id']))
        z2 += 1
    for j in range(HILF, HILF + 9):
        kv.column_dimensions[L(j)].width = 8

    # ---------- Diagramme ----------
    # Serienbeschriftungen liegen auf dem sichtbaren Grafikblatt, sonst
    # zeigt die Legende beim Rendern ins Leere
    lbl_sp = 16          # Spalte P, ausserhalb des Druckbereichs
    lbl_lauf = [1]

    def beschrifte(race_ids):
        zeilen = []
        for rid in race_ids:
            r0 = lbl_lauf[0]
            gr.cell(r0, lbl_sp, label_von.get(rid, '')).font = Font(name=ARIAL, size=9)
            zeilen.append(r0)
            lbl_lauf[0] += 1
        gr.column_dimensions[L(lbl_sp)].width = 24
        return zeilen

    def linie(titel, y_titel, daten_zeilen, kat_zeile, min_sp, max_sp,
              lbl_zeilen, hoehe=8.2, breite=25):
        ch = LineChart()
        ch.title = titel
        ch.style = 2
        ch.y_axis.title = y_titel
        ch.height, ch.width = hoehe, breite
        ch.y_axis.majorGridlines = None
        ch.legend.position = 'b'
        for r0 in daten_zeilen:
            ch.add_data(Reference(kv, min_col=min_sp, max_col=max_sp, min_row=r0, max_row=r0),
                        from_rows=True, titles_from_data=False)
        ch.set_categories(Reference(kv, min_col=min_sp, max_col=max_sp,
                                    min_row=kat_zeile, max_row=kat_zeile))
        for k, se in enumerate(ch.series):
            se.tx = SeriesLabel(strRef=StrRef(f'Grafiken!${L(lbl_sp)}${lbl_zeilen[k]}'))
            se.smooth = False
        return ch

    if gap_zeilen:
        c1 = linie(f'Wo wird die Zeit gewonnen und verloren?   Referenz: {ref_name}'
                   '   ·   unter der Nulllinie = schneller',
                   'Sekunden', gap_zeilen, kat1, 2, 12,
                   beschrifte(list(lauf['race_id'])), hoehe=8.6, breite=26)
        c1.x_axis.title = 'Hürde'
        gr.add_chart(c1, 'A1')

    if prof_zeilen:
        c2 = linie('Ermüdungsprofil — Verlust gegenüber dem eigenen schnellsten Abschnitt',
                   'Sekunden langsamer', [r for r, _ in prof_zeilen], kopf2, 2, 10,
                   beschrifte([rid for _, rid in prof_zeilen]), hoehe=8.6, breite=26)
        c2.x_axis.title = 'Abschnitt'
        gr.add_chart(c2, 'A20')

    gr.page_setup.orientation = 'landscape'
    gr.page_setup.fitToWidth = 1
    gr.page_setup.fitToHeight = 1
    gr.sheet_properties.pageSetUpPr.fitToPage = True
    gr.print_area = 'A1:N38'
    kv.sheet_state = 'hidden'


    ws.freeze_panes = f'{L(C_SEG0)}9'
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = '7:8'
    ws.print_area = f'A1:{L(BREIT)}{letzte}'

    # Formeln zwischenspeichern (openpyxl selbst laesst <v> leer; Excel und
    # LibreOffice rechnen beim Oeffnen ohnehin neu, aber Apple Numbers zeigt
    # sonst 0 statt der echten Werte - siehe xlsx_cache.py).
    puffer = io.BytesIO()
    wb.save(puffer)
    fertig = injiziere_cache_werte(puffer.getvalue(), {'Saison': {
        ref: (wert, ist_text) for blatt, ref, wert, ist_text in formel_cache if blatt == 'Saison'
    }})
    if hasattr(ziel, 'write'):
        ziel.write(fertig)
    else:
        with open(ziel, 'wb') as f:
            f.write(fertig)
    return ziel, len(lauf), len(vgl)


if __name__ == '__main__':
    athlet = sys.argv[1] if len(sys.argv) > 1 else 'Lars'
    saison = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    quelle = sys.argv[3] if len(sys.argv) > 3 else 'data/master.csv'
    ziel = f'{athlet}_400mH_{saison}.xlsx'
    p, n, v = baue(load_master(quelle), athlet, saison, ziel)
    print(f'{p}  ({n} Saisonrennen, {v} Vergleichsrennen)')
