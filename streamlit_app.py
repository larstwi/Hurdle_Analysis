#für run Befehl: Zuerst immer Analysexx.xlsx umbenennen (Version eins höher und im Code überall ändern)
#source "/Users/xxx/Documents/Auswertung Läufe/Database_400mh/.venv/bin/activate"      
#streamlit run "/Users/xxx/Documents/Auswertung Läufe/400m Hürden/Hurdle_Analysis/streamlit_app.py"
#Resultate auf Github pushenq


from io import BytesIO
 
import altair as alt
import pandas as pd
import streamlit as st
 
DATA_FILE = "data/Analyse32.xlsx"
CHART_COLS = [4, 5, 8, 11, 14, 18, 21, 24, 27, 30, 33]
 
 
def load_data():
    data = pd.read_excel(DATA_FILE)
    if "Zeit" in data.columns:
        zeit = data["Zeit"].astype(str).str.strip().str.replace(",", ".", regex=False)
        data["Zeit"] = pd.to_numeric(zeit, errors="coerce")
    return data
 
 
def to_pdf(df):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    font, header_font = "Helvetica", "Helvetica-Bold"
    font_size, padding = 6, 2

    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, float):
            return f"{v:g}"
        return str(v)

    header = [str(c) for c in df.columns]
    rows = [[fmt(v) for v in row] for row in df.itertuples(index=False)]
    table_data = [header] + rows

    # Spaltenbreiten aus dem breitesten Zellinhalt berechnen
    col_widths = []
    for i in range(len(header)):
        w = max(
            stringWidth(table_data[r][i], header_font if r == 0 else font, font_size)
            for r in range(len(table_data))
        )
        col_widths.append(w + 2 * padding + 2)

    pagesize = landscape(A3)
    avail = pagesize[0] - 20 * mm
    total = sum(col_widths)
    if total > avail:  # proportional schrumpfen, falls zu breit
        scale = avail / total
        col_widths = [w * scale for w in col_widths]
        font_size = max(4, font_size * scale)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), header_font),
        ("FONTNAME", (0, 1), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#999999")),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize,
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
        title="Analyse 400m Hürden",
    )
    doc.build([Paragraph("Gefilterte Daten", getSampleStyleSheet()["Heading2"]), table])
    buffer.seek(0)
    return buffer
 
 
def show_row_differences(df, selected_row):
    numeric_cols = [
        col for col in df.select_dtypes(include="number").columns
        if col not in (df.columns[0], df.columns[-1])
    ]
    differences = df[numeric_cols].subtract(df.loc[selected_row, numeric_cols], axis=1)
    return pd.concat([df[["Jahr", "Name", "Wettkampf"]], differences], axis=1)
 
 
def sidebar_filters(data):
    st.sidebar.header("Filteroptionen")
 
    athletes = st.sidebar.multiselect("Athlet:in wählen", data["Name"].unique(), default=[])
    years = st.sidebar.multiselect(
        "Jahr wählen", data["Jahr"].unique(), default=list(data["Jahr"].unique())
    )
 
    def time_input(label, fallback):
        raw = st.sidebar.text_input(label, value=str(fallback))
        try:
            return float(raw) if raw else fallback
        except ValueError:
            st.sidebar.error(f"Bitte eine gültige Zahl für '{label}' eingeben.")
            return fallback
 
    min_time = time_input("Minimale Zeit (Sekunden)", float(data["Zeit"].min()))
    max_time = time_input("Maximale Zeit (Sekunden)", float(data["Zeit"].max()))
    show_dnf = st.sidebar.checkbox("DNF anzeigen", value=False)
 
    return athletes, years, min_time, max_time, show_dnf
 
 
def filter_data(data, athletes, years, min_time, max_time, show_dnf):
    base = data["Name"].isin(athletes) & data["Jahr"].isin(years)
    time_mask = data["Zeit"].between(min_time, max_time)
    if show_dnf:
        time_mask |= data["Zeit"].isna()
    return data[base & time_mask]
 
 
def render_table(filtered_data):
    st.subheader("Datenübersicht (zum Vergleich eine Zeile auswählen)")
 
    table = filtered_data.copy()
    table.insert(0, "Auswählen", False)
 
    edited = st.data_editor(
        table, num_rows="dynamic", use_container_width=True, key="row_selector"
    )
    selected = edited[edited["Auswählen"]].index.tolist()
 
    if len(selected) > 1:
        st.warning("Bitte nur eine Zeile auswählen.")
        return
    if not selected:
        st.info("Wähle eine Zeile aus, um die Differenzen anzuzeigen.")
        return
 
    row = selected[0]
    name, wettkampf, jahr = filtered_data.loc[row, ["Name", "Wettkampf", "Jahr"]]
    st.markdown(f"### Differenzen relativ zu: {name} - {wettkampf} {jahr}")
    st.dataframe(show_row_differences(filtered_data, row))
 
 
def render_chart(filtered_data):
    cols = filtered_data.iloc[:, CHART_COLS].copy()
    order = cols.columns.tolist()
    cols["Wettkampf"] = filtered_data["Name"] + " - " + filtered_data["Wettkampf"]
 
    melted = cols.melt(
        id_vars=["Wettkampf"], var_name="Abschnitt", value_name="Abschnittszeit"
    )
 
    chart = (
        alt.Chart(melted)
        .mark_line()
        .encode(
            x=alt.X("Abschnitt:O", sort=order),
            y="Abschnittszeit:Q",
            color="Wettkampf:N",
            tooltip=["Wettkampf", "Abschnitt", "Abschnittszeit"],
        )
        .properties(title="Abschnittszeiten")
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)
 
 
def render_export(filtered_data):
    st.header("Exportieren")
    export_format = st.selectbox("Exportformat wählen", ["CSV", "Excel", "PDF"])
 
    if not st.button("Exportieren"):
        return
 
    if export_format == "CSV":
        st.download_button(
            "Download CSV",
            filtered_data.to_csv(index=False).encode("utf-8"),
            file_name="filtered_data.csv",
            mime="text/csv",
        )
 
    elif export_format == "Excel":
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            filtered_data.to_excel(writer, index=False, sheet_name="Sheet1")
        st.download_button(
            "Download Excel",
            buffer.getvalue(),
            file_name="filtered_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
 
    elif export_format == "PDF":
        try:
            st.download_button(
                "Download PDF",
                to_pdf(filtered_data),
                file_name="filtered_data.pdf",
                mime="application/pdf",
            )
        except ModuleNotFoundError:
            st.error("PDF-Export benötigt reportlab: pip install reportlab")
 
 
def main():
    st.title("Analyse 400m Hürden")
    data = load_data()
 
    filters = sidebar_filters(data)
    filtered_data = filter_data(data, *filters)
 
    render_table(filtered_data)
    render_chart(filtered_data)
    render_export(filtered_data)
 
 
if __name__ == "__main__":
    main()