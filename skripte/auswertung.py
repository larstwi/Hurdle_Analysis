#!/usr/bin/env python3
"""Gemeinsame Auswertungslogik fuer Excel- und PDF-Export.

Beide Exportformen muessen exakt dieselbe Saisonbestzeit, persoenliche
Bestzeit, Referenz und Vergleichsrennen zeigen. Das wird hier einmal
berechnet und von athletenblatt.py und pdf_export.py gleichermassen benutzt.
"""

import pandas as pd


def select_season(master, athlet, saison, vergleiche=4):
    """Waehlt Saisonrennen, Vergleichsrennen und Kennzahlen fuer einen Athleten.

    Rueckgabe als Dict:
      lauf        - Saisonrennen, chronologisch
      vgl         - Vergleichsrennen aus Vorjahren, neuestes Jahr zuerst
      sb, pb      - Saisonbestzeit, persoenliche Bestzeit (float oder NaN)
      pb_jahr     - Jahr der PB
      pb_id       - race_id der PB
      ref         - Referenzrennen fuer den Rueckstand-Chart (schnellstes
                    vollstaendiges Saisonrennen), als Series oder None
    """
    alle = master[master['athlet'] == athlet].copy()
    if alle.empty:
        raise ValueError(f'Keine Rennen fuer {athlet} gefunden.')
    if '_jahr' not in alle.columns:
        alle['_jahr'] = pd.to_datetime(alle['datum'], errors='coerce').dt.year

    lauf = alle[alle['_jahr'] == saison].sort_values('datum')
    if lauf.empty:
        raise ValueError(f'Keine Rennen fuer {athlet} in {saison}.')
    frueher = alle[alle['_jahr'] < saison].copy()

    zeiten = pd.to_numeric(lauf['zeit'], errors='coerce')
    sb = zeiten.min()
    alle_z = pd.to_numeric(alle['zeit'], errors='coerce')
    pb = alle_z.min()
    pb_jahr = int(alle.loc[alle_z.idxmin(), '_jahr']) if pd.notna(pb) else None
    pb_id = alle.loc[alle_z.idxmin(), 'race_id'] if pd.notna(pb) else None

    vgl = pd.DataFrame()
    if not frueher.empty:
        frueher['_zeit'] = pd.to_numeric(frueher['zeit'], errors='coerce')
        g = frueher.dropna(subset=['_zeit'])
        if not g.empty:
            beste = g.loc[g.groupby('_jahr')['_zeit'].idxmin()]
            rest = g.drop(beste.index)
            if pd.notna(sb) and not rest.empty and len(beste) < vergleiche:
                rest = rest.assign(_d=(rest['_zeit'] - sb).abs()).nsmallest(
                    vergleiche - len(beste), '_d')
                vgl = pd.concat([beste, rest])
            else:
                vgl = beste
            vgl = vgl.sort_values('datum', ascending=False)

    vollstaendig = [r for _, r in lauf.iterrows()
                    if r['status'] == 'OK' and all(pd.notna(r[f'h{i}']) for i in range(1, 11))]
    ref = min(vollstaendig, key=lambda r: float(r['zeit'])) if vollstaendig else None

    return {
        'lauf': lauf, 'vgl': vgl, 'sb': sb, 'pb': pb,
        'pb_jahr': pb_jahr, 'pb_id': pb_id, 'ref': ref,
    }


def segmente(row):
    """Abschnittszeiten (Start-H1, 9x35m, H10-Ziel) und Schrittzahlen einer Zeile.

    Werte, die fehlen, werden als None gefuehrt statt Fehler zu werfen -
    unvollstaendige Rennen (z.B. wegen verdeckter Huerde) sind normal.
    """
    def f(v):
        return None if v is None or (isinstance(v, float) and pd.isna(v)) else float(v)

    h = [f(row.get(f'h{i}')) for i in range(1, 11)]
    z = f(row.get('zeit'))

    seg = [h[0]]
    for i in range(9):
        seg.append(None if h[i] is None or h[i + 1] is None else round(h[i + 1] - h[i], 3))
    seg.append(None if h[9] is None or z is None else round(z - h[9], 3))

    s = [row.get('s_start')] + [row.get(f's{i}_{i+1}') for i in range(1, 10)]
    s = [None if (v is None or (isinstance(v, float) and pd.isna(v))) else int(v) for v in s]
    return seg, s


def abschnittsbezeichnung(i):
    """Ueberschrift fuer Abschnitt i (0 = Start-H1 ... 9 = H10-Ziel)."""
    if i == 0:
        return 'Start–H1'
    if i == 9:
        return 'H10–Ziel'
    return f'H{i}–H{i+1}'


def kuerzel_runde(runde, lauf):
    """'Vorlauf' -> 'V', 'Trainingswettkampf' + Lauf 2 -> 'T2', usw."""
    KUERZEL = {'Vorlauf': 'V', 'Halbfinal': 'H', 'Final': 'F', 'Trainingswettkampf': 'T'}
    if not runde or (isinstance(runde, float) and pd.isna(runde)):
        return ''
    k = KUERZEL.get(str(runde), '')
    if k and lauf not in (None, '') and not (isinstance(lauf, float) and pd.isna(lauf)):
        k = f'{k}{int(lauf)}'
    return k


def label(row):
    """Kurzbezeichnung eines Rennens fuer Legenden: '28.06. Bellinzona T1'."""
    datum = pd.to_datetime(row['datum']).strftime('%d.%m.') if pd.notna(row.get('datum')) else '?'
    ort = row.get('ort') or ''
    k = kuerzel_runde(row.get('runde'), row.get('lauf'))
    return f'{datum} {ort} {k}'.rstrip()
