"""400 m Hürden — Saisonauswertung.

Liest data/master.csv (einzige Datenquelle, wird vom Markier-Tool per
GitHub-Commit aktualisiert). Bietet drei Ansichten:
  Athlet      - Saisonuebersicht mit Excel- und PDF-Download
  Vergleich   - beliebige Rennen gegeneinander
  Alle Daten  - gefilterte Rohtabelle mit CSV-Export

Lauf lokal: streamlit run streamlit_app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / 'skripte'))

from master_io import load_master                                  # noqa: E402
from auswertung import select_season, label                        # noqa: E402
from export_utils import xlsx_bytes, pdf_bytes, pdf_bytes_auswahl        # noqa: E402
from pdf_export import grafik_rueckstand, grafik_ermuedung          # noqa: E402
from html_tabelle import rennen_tabelle_html                        # noqa: E402

DATA_FILE = Path(__file__).parent / 'data' / 'master.csv'

st.set_page_config(page_title='400 m Hürden — Auswertung', layout='wide')


# ---------------------------------------------------------------- Daten
@st.cache_data(ttl=60)
def get_master():
    return load_master(str(DATA_FILE))


@st.cache_data(ttl=60, show_spinner='Excel wird erstellt …')
def get_xlsx(athlet, saison, _stand):
    return xlsx_bytes(get_master(), athlet, saison)


@st.cache_data(ttl=60, show_spinner='PDF wird erstellt …')
def get_pdf(athlet, saison, _stand):
    return pdf_bytes(get_master(), athlet, saison)


@st.cache_data(ttl=60, show_spinner='PDF wird erstellt …')
def get_pdf_auswahl(race_ids, titel, _stand):
    return pdf_bytes_auswahl(get_master(), list(race_ids), titel)


def datenstand(master):
    """Aendert sich der Rueckgabewert, verfaellt der Export-Cache automatisch."""
    return (len(master), str(master['erfasst_am'].max()))


# ---------------------------------------------------------------- Anzeige
def kpi_zeile(auswahl, lauf):
    sb, pb = auswahl['sb'], auswahl['pb']
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric('Saisonbestzeit', f'{sb:.2f} s' if pd.notna(sb) else '—')
    c2.metric('Persönliche Bestzeit', f'{pb:.2f} s' if pd.notna(pb) else '—')
    c3.metric('Jahr der PB', str(auswahl['pb_jahr']) or '—')
    c4.metric('Rennen in der Saison', str(len(lauf)))
    c5.metric('Beendet', str(int((lauf['status'] == 'OK').sum())))


def rennen_tabelle(rennen, pb_id, vgl=False):
    """Tabelle im PDF-/Excel-Layout: zwei Zeilen pro Rennen, Abschnitte und
    Schritte je Huerdenabschnitt in eigenen Spalten, PB goldumrandet."""
    html = rennen_tabelle_html(rennen, pb_id, vgl=vgl)
    if html:
        st.markdown(html, unsafe_allow_html=True)


def tab_athlet(master):
    athleten = sorted(master['athlet'].dropna().unique())
    c1, c2 = st.columns([2, 1])
    athlet = c1.selectbox('Athlet:in', athleten)

    jahre = sorted(master.loc[master['athlet'] == athlet, '_jahr'].dropna().unique().astype(int),
                   reverse=True)
    if not jahre:
        st.info(f'Keine Rennen für {athlet}.')
        return
    saison = c2.selectbox('Saison', jahre)

    try:
        auswahl = select_season(master, athlet, saison)
    except ValueError as e:
        st.warning(str(e))
        return

    kpi_zeile(auswahl, auswahl['lauf'])
    st.caption('🏅 = persönliche Bestzeit')

    st.subheader('Saison')
    rennen_tabelle(auswahl['lauf'], auswahl['pb_id'])

    if not auswahl['vgl'].empty:
        st.subheader('Vergleich frühere Jahre')
        st.caption('Bestes Rennen je Saison, neuestes zuerst')
        rennen_tabelle(auswahl['vgl'], auswahl['pb_id'], vgl=True)

    st.subheader('Grafiken')
    col1, col2 = st.columns(2)
    bild1 = grafik_rueckstand(auswahl['lauf'], auswahl['ref'])
    bild2 = grafik_ermuedung(pd.concat([auswahl['lauf'], auswahl['vgl']]))
    if bild1:
        col1.image(bild1, width='stretch')
    else:
        col1.info('Keine vollständige Referenz für diese Saison gefunden.')
    if bild2:
        col2.image(bild2, width='stretch')

    st.subheader('Export')
    stand = datenstand(master)
    c1, c2 = st.columns(2)
    c1.download_button(
        '⬇ Excel herunterladen', get_xlsx(athlet, saison, stand),
        file_name=f'{athlet}_400mH_{saison}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        width='stretch')
    c2.download_button(
        '⬇ PDF herunterladen', get_pdf(athlet, saison, stand),
        file_name=f'{athlet}_400mH_{saison}.pdf', mime='application/pdf',
        width='stretch')


def tab_vergleich(master):
    st.caption('Beliebige Rennen gegeneinander – auch über Athleten und Jahre hinweg. '
              'Zum Beispiel Lauf A, B und C zusammenstellen und als PDF mitnehmen.')

    m = master.dropna(subset=['datum']).copy()
    m['_label'] = m.apply(lambda r: f"{r['athlet']} — {label(r)} ({r['zeit']:.2f} s)"
                          if pd.notna(r['zeit']) else f"{r['athlet']} — {label(r)} ({r['status']})",
                          axis=1)
    optionen = dict(zip(m['_label'], m['race_id']))

    gewaehlt = st.multiselect('Rennen wählen (2–10)', list(optionen.keys()), max_selections=10)
    if len(gewaehlt) < 2:
        st.info('Mindestens zwei Rennen auswählen.')
        return

    ids = [optionen[g] for g in gewaehlt]
    auswahl = m[m['race_id'].isin(ids)]
    # Reihenfolge der Auswahl beibehalten, nicht die zufaellige Tabellenreihenfolge
    auswahl = auswahl.set_index('race_id').loc[ids].reset_index()
    auswahl = auswahl.assign(_label=gewaehlt)

    zeitwerte = pd.to_numeric(auswahl['zeit'], errors='coerce')
    ref = None
    if zeitwerte.notna().any():
        vorschlag = int(zeitwerte.idxmin())
        ref_label = st.selectbox('Referenz für den Rückstand-Chart', gewaehlt, index=vorschlag)
        ref = auswahl[auswahl['_label'] == ref_label].iloc[0]

    col1, col2 = st.columns(2)
    bild1 = grafik_rueckstand(auswahl, ref)
    bild2 = grafik_ermuedung(auswahl)
    if bild1:
        col1.image(bild1, width='stretch')
    if bild2:
        col2.image(bild2, width='stretch')

    st.subheader('Rennen im Vergleich')
    rennen_tabelle(auswahl, None)

    st.subheader('Export')
    titel = st.text_input('Titel für das PDF', value='Rennvergleich')
    stand = datenstand(master)
    st.download_button(
        '⬇ Auswahl als PDF herunterladen',
        get_pdf_auswahl(tuple(ids), titel, stand),
        file_name=f'{titel.strip().replace(" ", "_") or "Rennvergleich"}.pdf',
        mime='application/pdf', width='stretch')


def tab_alle_daten(master):
    st.caption('Alle erfassten Rennen, filterbar. Für eigene Auswertungen als CSV exportierbar.')

    c1, c2, c3 = st.columns(3)
    athleten = c1.multiselect('Athlet:in', sorted(master['athlet'].dropna().unique()))
    jahre = c2.multiselect('Jahr', sorted(master['_jahr'].dropna().unique().astype(int), reverse=True))
    nur_ok = c3.checkbox('Nur beendete Rennen', value=False)

    gefiltert = master.copy()
    if athleten:
        gefiltert = gefiltert[gefiltert['athlet'].isin(athleten)]
    if jahre:
        gefiltert = gefiltert[gefiltert['_jahr'].isin(jahre)]
    if nur_ok:
        gefiltert = gefiltert[gefiltert['status'] == 'OK']

    anzeige_spalten = ['datum', 'athlet', 'ort', 'serie', 'runde', 'lauf', 'bahn',
                       'rang', 'zeit', 'status'] + [f'h{i}' for i in range(1, 11)]
    st.dataframe(gefiltert[anzeige_spalten], width='stretch', hide_index=True)
    st.caption(f'{len(gefiltert)} von {len(master)} Rennen')

    st.download_button(
        '⬇ Gefilterte Daten als CSV', gefiltert[anzeige_spalten].to_csv(index=False).encode('utf-8'),
        file_name='400mh_export.csv', mime='text/csv')


# ---------------------------------------------------------------- Hauptseite
def main():
    st.title('400 m Hürden — Saisonauswertung')

    if not DATA_FILE.exists():
        st.error(f'Datendatei nicht gefunden: {DATA_FILE}')
        return
    master = get_master()

    tab1, tab2, tab3 = st.tabs(['Athlet', 'Vergleich', 'Alle Daten'])
    with tab1:
        tab_athlet(master)
    with tab2:
        tab_vergleich(master)
    with tab3:
        tab_alle_daten(master)


if __name__ == '__main__':
    main()
