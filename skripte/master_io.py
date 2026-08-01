#!/usr/bin/env python3
"""Liest und schreibt den zentralen Master unter data/master.csv.

Das ist ab jetzt die einzige Datenquelle. xlsx-Import (daten.py) war ein
einmaliger Schritt, um den alten Analyse32.xlsx-Bestand ins Zielschema
zu bringen. Alles Neue kommt ueber das Markier-Tool direkt in dieses CSV.
"""

import pandas as pd

SCHEMA = (['race_id', 'datum', 'athlet', 'ort', 'serie', 'runde', 'lauf',
           'bahn', 'rang', 'zeit', 'status', 'fps', 'quelle', 'erfasst_am',
           'video', 'notiz', 'roh_wettkampf']
          + [f'h{i}' for i in range(1, 11)]
          + ['s_start'] + [f's{i}_{i+1}' for i in range(1, 10)])

# Spalten, die als Zahl gefuehrt werden - Rest bleibt Text
NUMERISCH = (['lauf', 'bahn', 'rang', 'zeit', 'fps']
             + [f'h{i}' for i in range(1, 11)]
             + ['s_start'] + [f's{i}_{i+1}' for i in range(1, 10)])


def load_master(pfad='data/master.csv'):
    """Laedt den Master und erzwingt konsistente Typen.

    Leere Zellen werden zu NaN (nicht zu leeren Strings), damit pandas'
    numerische Funktionen (min, idxmin, Vergleiche) direkt funktionieren.
    """
    df = pd.read_csv(pfad, dtype=str, keep_default_na=False, na_values=[''])
    for c in SCHEMA:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[SCHEMA]
    for c in NUMERISCH:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['_jahr'] = pd.to_datetime(df['datum'], errors='coerce').dt.year
    return df


def save_master(df, pfad='data/master.csv'):
    """Schreibt den Master zurueck, sortiert nach Athlet und Datum.

    Leere Werte werden als leere Zellen geschrieben (nicht 'nan' oder 'NaT'),
    damit das CSV auch von Hand oder in Numbers lesbar bleibt.
    """
    out = df[SCHEMA].sort_values(['athlet', 'datum'], kind='stable').reset_index(drop=True)
    out.to_csv(pfad, index=False, encoding='utf-8', na_rep='')
    return out


def upsert(df, neue_rennen):
    """Fuegt Rennen ein oder ersetzt sie anhand von race_id.

    neue_rennen: Liste von Dicts im SCHEMA-Format (fehlende Felder erlaubt).
    Gibt (aktualisiertes df, Liste neuer race_id, Liste ersetzter race_id) zurueck.
    """
    df = df.drop(columns=['_jahr'], errors='ignore').copy()
    neu_ids, ersetzt_ids = [], []
    for rennen in neue_rennen:
        rid = rennen.get('race_id')
        if not rid:
            raise ValueError('Rennen ohne race_id kann nicht gespeichert werden.')
        zeile = {c: rennen.get(c, pd.NA) for c in SCHEMA}
        treffer = df.index[df['race_id'] == rid]
        if len(treffer):
            df.loc[treffer[0]] = zeile
            ersetzt_ids.append(rid)
        else:
            df = pd.concat([df, pd.DataFrame([zeile])], ignore_index=True)
            neu_ids.append(rid)
    for c in NUMERISCH:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['_jahr'] = pd.to_datetime(df['datum'], errors='coerce').dt.year
    return df, neu_ids, ersetzt_ids


if __name__ == '__main__':
    d = load_master()
    print(f'{len(d)} Rennen, {d["athlet"].nunique()} Athleten, '
          f'{int(d["_jahr"].min())}\u2013{int(d["_jahr"].max())}')
