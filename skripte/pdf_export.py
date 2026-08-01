#!/usr/bin/env python3
"""Erzeugt das PDF-Pendant zum Athletenblatt.

Nutzt select_season() aus auswertung.py - dieselbe PB, dieselbe Referenz,
dieselben Vergleichsrennen wie im Excel-Export. Die beiden Formate koennen
dadurch nie auseinanderlaufen.
"""

import io
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                 Spacer, Image, KeepTogether, PageBreak)

from master_io import load_master
from auswertung import select_season, segmente, abschnittsbezeichnung, label

# Liberation Sans ist metrisch mit Arial/Helvetica kompatibel - so wirken die
# matplotlib-Diagramme wie aus einem Guss mit der Helvetica-Tabelle daneben,
# statt wie ein Fremdkoerper in der matplotlib-Standardschrift (DejaVu Sans).
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Liberation Sans', 'Arial', 'Helvetica', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

TINTE = colors.HexColor('#1F3348')
GRAU = colors.HexColor('#6B7A8A')
GOLD = colors.HexColor('#B8860B')
GOLD_HELL = colors.HexColor('#FBF0CE')
SCHRITTZEILE = colors.HexColor('#EDF1F5')
RAND = colors.HexColor('#B8C4D0')
VERGLEICH_TEXT = colors.HexColor('#5A6B7C')

# Dieselbe Palette wie im Markier-Tool (BAHNFARBEN) - damit Live-Vorschau,
# xlsx-Kontext und PDF optisch zur selben Familie gehoeren statt matplotlibs
# generischer Standardfarben (Blau/Orange/Gruen/Rot/Lila).
LINIENFARBEN = ['#C8571F', '#2E7D6B', '#3B6FA0', '#A0439B', '#B8860B',
                '#5E8C3F', '#B34A5C', '#3F8C8C', '#6B5B95']

SPALTEN = (['Datum', 'Ort', 'Rd', 'Bahn', 'Rang', 'Zeit', '0–200', '200–400', 'Diff']
           + ['Start–H1'] + [f'H{i}–H{i+1}' for i in range(1, 10)] + ['H10–Ziel'])


def fmt(v, nachkomma=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    if isinstance(v, str):
        return v
    return f'{v:.{nachkomma}f}'


def kurz(row):
    from auswertung import kuerzel_runde
    return kuerzel_runde(row.get('runde'), row.get('lauf'))


def zeitzeile(row):
    if row['status'] != 'OK':
        return str(row['status'])
    return fmt(row['zeit'])


def h200_h400_diff(row):
    h5, h6, zeit = row.get('h5'), row.get('h6'), row.get('zeit')
    if pd.isna(h5) or pd.isna(h6):
        return None, None, None
    m200 = h5 + (h6 - h5) * 14 / 35
    if pd.isna(zeit):
        return round(m200, 2), None, None
    m400 = zeit - m200
    return round(m200, 2), round(m400, 2), round(m400 - m200, 2)


def rennzeilen(row, mit_athlet=False):
    """Zwei Tabellenzeilen (Zeit, Schritte) fuer ein Rennen.

    mit_athlet=True stellt den Namen voran - noetig, wenn eine Tabelle
    Rennen verschiedener Athlet:innen nebeneinander zeigt.
    """
    seg, schritte = segmente(row)
    m200, m400, diff = h200_h400_diff(row)
    kopf = [row.get('athlet') or ''] if mit_athlet else []
    kopf += [str(pd.to_datetime(row['datum']).strftime('%d.%m.%Y')) if pd.notna(row['datum']) else '',
            row.get('ort') or '', kurz(row),
            fmt(row.get('bahn'), 0), fmt(row.get('rang'), 0)]
    zeile1 = kopf + [zeitzeile(row), fmt(m200), fmt(m400),
                     ('+' if diff and diff > 0 else '') + fmt(diff) if diff is not None else ''] \
             + [fmt(v) for v in seg]
    leer = [''] * (6 if mit_athlet else 5)
    zeile2 = leer + [''] * 4 + [fmt(v, 0) if v is not None else '' for v in schritte]
    return zeile1, zeile2


def grafikseite(doc, bild1, bild2):
    """Beide Diagramme zusammen auf einer eigenen Seite, gross und mittig.

    Vorher lag jedes Diagramm einzeln bei 35% der Seitenhoehe, oft ueber zwei
    Seiten verteilt (eines gequetscht unter der Tabelle, eines allein auf der
    naechsten, grossteils leeren Seite). Jetzt: erzwungener Seitenumbruch,
    beide Bilder auf voller Breite gestapelt - nutzt die A3-Seite tatsaechlich.
    """
    elemente = [e for e in (bild1, bild2) if e]
    if not elemente:
        return []
    breite = doc.width * 0.78
    hoehe = breite * 0.40   # entspricht dem matplotlib-Seitenverhaeltnis (9 x 3.6)
    story = [PageBreak()]
    for i, bild in enumerate(elemente):
        story.append(Image(bild, width=breite, height=hoehe))
        if i < len(elemente) - 1:
            story.append(Spacer(1, 14))
    return story


def baue_pdf(master, athlet, saison, vergleiche=4):
    auswahl = select_season(master, athlet, saison, vergleiche)
    lauf, vgl = auswahl['lauf'], auswahl['vgl']
    sb, pb, pb_jahr, pb_id = auswahl['sb'], auswahl['pb'], auswahl['pb_jahr'], auswahl['pb_id']

    buffer = io.BytesIO()
    pagesize = landscape(A3)
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
        title=f'{athlet} – 400 m Hürden – Saison {saison}')

    styles = {
        'titel': ParagraphStyle('titel', fontName='Helvetica-Bold', fontSize=18,
                                textColor=colors.white, leading=22),
        'kpi_l': ParagraphStyle('kpi_l', fontName='Helvetica', fontSize=8, textColor=GRAU),
        'kpi_v': ParagraphStyle('kpi_v', fontName='Helvetica-Bold', fontSize=13, textColor=TINTE),
        'hinweis': ParagraphStyle('hinweis', fontName='Helvetica', fontSize=7.5, textColor=GRAU),
        'block': ParagraphStyle('block', fontName='Helvetica-Bold', fontSize=8.5,
                                textColor=colors.white),
    }

    story = []

    kopf_tbl = Table([[Paragraph(f'{athlet.upper()}   ·   400 M HÜRDEN   ·   SAISON {saison}',
                                 styles['titel'])]], colWidths=[doc.width])
    kopf_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TINTE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(kopf_tbl)
    story.append(Spacer(1, 4))

    kpis = [('Saisonbestzeit', f'{sb:.2f} s' if pd.notna(sb) else '—'),
            ('Persönliche Bestzeit', f'{pb:.2f} s' if pd.notna(pb) else '—'),
            ('Jahr', str(pb_jahr) if pb_jahr else '—'),
            ('Rennen in der Saison', str(len(lauf))),
            ('Beendet', str(int((lauf['status'] == 'OK').sum())))]
    kpi_row = [[Paragraph(t, styles['kpi_l'])] + [Paragraph(w, styles['kpi_v'])]
               for t, w in kpis]
    kpi_tbl = Table([[Paragraph(t, styles['kpi_l']) for t, _ in kpis],
                     [Paragraph(w, styles['kpi_v']) for _, w in kpis]],
                    colWidths=[doc.width / len(kpis)] * len(kpis))
    kpi_tbl.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 2),
                                 ('TOPPADDING', (0, 0), (-1, -1), 1)]))
    story.append(kpi_tbl)
    story.append(Paragraph('Je Rennen zwei Zeilen: oben die Abschnittszeit, darunter die '
                           'Schrittzahl im gleichen Abschnitt.   Goldener Rahmen = '
                           'persönliche Bestzeit.', styles['hinweis']))
    story.append(Spacer(1, 6))

    # ---------- Tabelle ----------
    daten = [SPALTEN]
    zeilen_meta = []   # (zeile_index_zeit, ist_pb, ist_vergleich)
    for _, r in lauf.iterrows():
        z1, z2 = rennzeilen(r)
        zeilen_meta.append((len(daten), r['race_id'] == pb_id, False))
        daten += [z1, z2]
    if not vgl.empty:
        daten.append(['VERGLEICH FRÜHERE JAHRE · bestes Rennen je Saison, neuestes zuerst']
                     + [''] * (len(SPALTEN) - 1))
        vgl_kopf_idx = len(daten) - 1
        for _, r in vgl.iterrows():
            z1, z2 = rennzeilen(r)
            zeilen_meta.append((len(daten), r['race_id'] == pb_id, True))
            daten += [z1, z2]
    else:
        vgl_kopf_idx = None

    n_r, n_c = len(daten), len(SPALTEN)
    breiten = [22, 30, 10, 12, 12, 14, 14, 14, 13] + [15] + [13] * 9 + [15]
    skala = doc.width / sum(breiten)
    breiten = [b * skala for b in breiten]

    tbl = Table(daten, colWidths=breiten, repeatRows=1)
    stil = [
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DCE3EA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), TINTE),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
        ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, RAND),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    for i, (r0, ist_pb, ist_vgl) in enumerate(zeilen_meta):
        stil.append(('SPAN', (0, r0), (0, r0 + 1)))
        stil.append(('SPAN', (1, r0), (1, r0 + 1)))
        for c in (2, 3, 4, 5, 6, 7, 8):
            stil.append(('SPAN', (c, r0), (c, r0 + 1)))
        stil.append(('BACKGROUND', (0, r0 + 1), (-1, r0 + 1), SCHRITTZEILE))
        stil.append(('FONTNAME', (5, r0), (5, r0), 'Helvetica-Bold'))
        if ist_vgl:
            stil.append(('TEXTCOLOR', (0, r0), (-1, r0), VERGLEICH_TEXT))
            stil.append(('FONTNAME', (0, r0), (1, r0), 'Helvetica-Oblique'))
        if ist_pb:
            stil.append(('BOX', (0, r0), (-1, r0 + 1), 1.4, GOLD))
            stil.append(('BACKGROUND', (0, r0), (1, r0), GOLD_HELL))
    if vgl_kopf_idx is not None:
        stil.append(('SPAN', (0, vgl_kopf_idx), (-1, vgl_kopf_idx)))
        stil.append(('BACKGROUND', (0, vgl_kopf_idx), (-1, vgl_kopf_idx), GRAU))
        stil.append(('TEXTCOLOR', (0, vgl_kopf_idx), (-1, vgl_kopf_idx), colors.white))
        stil.append(('FONTNAME', (0, vgl_kopf_idx), (-1, vgl_kopf_idx), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(stil))
    story.append(tbl)
    story.append(Spacer(1, 10))

    # ---------- Grafiken ----------
    reihenfolge = pd.concat([lauf, vgl]) if not vgl.empty else lauf
    bild1 = grafik_rueckstand(lauf, auswahl['ref'])
    bild2 = grafik_ermuedung(reihenfolge)
    story += grafikseite(doc, bild1, bild2)

    doc.build(story)
    buffer.seek(0)
    return buffer


def baue_pdf_auswahl(master, race_ids, titel='Rennvergleich'):
    """PDF fuer eine frei zusammengestellte Rennauswahl - unabhaengig von
    Athlet oder Saison. Fuer den Vergleich-Reiter: Trainer waehlen einzelne
    Rennen (auch verschiedener Athlet:innen) und exportieren die Auswahl."""
    rows = master[master['race_id'].isin(race_ids)].copy()
    if rows.empty:
        raise ValueError('Keine der gewaehlten Rennen wurde im Master gefunden.')
    rows['_ord'] = rows['race_id'].map({r: i for i, r in enumerate(race_ids)})
    rows = rows.sort_values('_ord')

    vollstaendig = [r for _, r in rows.iterrows()
                    if r['status'] == 'OK' and all(pd.notna(r[f'h{i}']) for i in range(1, 11))]
    ref = min(vollstaendig, key=lambda r: float(r['zeit'])) if vollstaendig else None

    buffer = io.BytesIO()
    pagesize = landscape(A3)
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
        title=titel)

    styles = {
        'titel': ParagraphStyle('titel', fontName='Helvetica-Bold', fontSize=18,
                                textColor=colors.white, leading=22),
        'hinweis': ParagraphStyle('hinweis', fontName='Helvetica', fontSize=7.5, textColor=GRAU),
    }
    story = []

    kopf_tbl = Table([[Paragraph(titel.upper() + '   ·   400 M HÜRDEN', styles['titel'])]],
                     colWidths=[doc.width])
    kopf_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), TINTE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(kopf_tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f'{len(rows)} frei gewählte Rennen.   Je Rennen zwei Zeilen: oben die '
                           'Abschnittszeit, darunter die Schrittzahl im gleichen Abschnitt.',
                           styles['hinweis']))
    story.append(Spacer(1, 6))

    spalten = ['Läufer:in'] + SPALTEN
    daten = [spalten]
    for _, r in rows.iterrows():
        z1, z2 = rennzeilen(r, mit_athlet=True)
        daten += [z1, z2]

    breiten = [26, 22, 30, 10, 12, 12, 14, 14, 14, 13] + [15] + [13] * 9 + [15]
    skala = doc.width / sum(breiten)
    breiten = [b * skala for b in breiten]

    tbl = Table(daten, colWidths=breiten, repeatRows=1)
    stil = [
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DCE3EA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), TINTE),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
        ('ALIGN', (4, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (2, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, RAND),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    for i in range(len(rows)):
        r0 = 1 + i * 2
        for c in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
            stil.append(('SPAN', (c, r0), (c, r0 + 1)))
        stil.append(('BACKGROUND', (0, r0 + 1), (-1, r0 + 1), SCHRITTZEILE))
        stil.append(('FONTNAME', (6, r0), (6, r0), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(stil))
    story.append(tbl)
    story.append(Spacer(1, 10))

    bild1 = grafik_rueckstand(rows, ref)
    bild2 = grafik_ermuedung(rows)
    story += grafikseite(doc, bild1, bild2)

    doc.build(story)
    buffer.seek(0)
    return buffer


def _stil_achse(ax):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#B8C4D0')
    ax.spines['bottom'].set_color('#B8C4D0')
    ax.tick_params(colors='#3D4B59', labelsize=8.5)
    ax.grid(axis='y', color='#D8DEE4', linewidth=0.9)
    ax.set_axisbelow(True)


def grafik_rueckstand(lauf, ref):
    if ref is None or lauf.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=150)
    x = list(range(1, 12))
    xt = [f'H{i}' for i in range(1, 11)] + ['Ziel']
    ref_h = [ref.get(f'h{i}') for i in range(1, 11)] + [ref.get('zeit')]

    for i, (_, r) in enumerate(lauf.iterrows()):
        h = [r.get(f'h{i}') for i in range(1, 11)] + [r.get('zeit')]
        y = [(a - b) if pd.notna(a) and pd.notna(b) else float('nan')
             for a, b in zip(h, ref_h)]
        ax.plot(x, y, marker='o', markersize=3, linewidth=2.0,
                color=LINIENFARBEN[i % len(LINIENFARBEN)], label=label(r))

    ax.axhline(0, color='#B3261E', linewidth=1.2, alpha=0.55)
    ax.set_xticks(x, xt)
    ax.set_ylabel('Sekunden', fontsize=8.5)
    ref_name = f"{pd.to_datetime(ref['datum']).strftime('%d.%m.%y')} {ref['ort']} — {float(ref['zeit']):.2f} s"
    ax.set_title(f'Wo wird die Zeit gewonnen und verloren?   Referenz: {ref_name}   ·   '
                'unter der Nulllinie = schneller', fontsize=11, fontweight='bold',
                color='#1F3348', pad=12)
    _stil_achse(ax)
    ax.legend(fontsize=8, frameon=False, loc='upper left', bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def grafik_ermuedung(rennen):
    if rennen.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=150)
    x = list(range(1, 10))
    xt = [f'H{i}–H{i+1}' for i in range(1, 10)]

    i = 0
    for _, r in rennen.iterrows():
        seg, _ = segmente(r)
        kern = [v for v in seg[1:10] if v is not None]
        if not kern:
            continue
        m = min(kern)
        y = [v - m if v is not None else float('nan') for v in seg[1:10]]
        ax.plot(x, y, marker='o', markersize=3, linewidth=2.0,
                color=LINIENFARBEN[i % len(LINIENFARBEN)], label=label(r))
        i += 1

    ax.set_xticks(x, xt)
    ax.set_ylabel('Sekunden langsamer', fontsize=8.5)
    ax.set_title('Ermüdungsprofil — Verlust gegenüber dem eigenen schnellsten Abschnitt',
                fontsize=11, fontweight='bold', color='#1F3348', pad=12)
    _stil_achse(ax)
    ax.legend(fontsize=8, frameon=False, loc='upper left', bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


if __name__ == '__main__':
    athlet = sys.argv[1] if len(sys.argv) > 1 else 'Lars'
    saison = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    quelle = sys.argv[3] if len(sys.argv) > 3 else 'data/master.csv'
    master = load_master(quelle)
    buf = baue_pdf(master, athlet, saison)
    ziel = f'{athlet}_400mH_{saison}.pdf'
    with open(ziel, 'wb') as f:
        f.write(buf.read())
    print(ziel)
