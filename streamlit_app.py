import streamlit as st
import pandas as pd

# Funktion zum Laden der Daten
@st.cache
def load_data():
    data = pd.read_excel('data/Analyse10.xlsx')
    return data


# Funktion zum PDF-Export
def to_pdf(df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Überschrift
    c.drawString(30, height - 40, "Gefilterte Daten")

    # Tabellenkopf
    col_width = width / len(df.columns)
    row_height = 20
    y = height - 60
    for col in df.columns:
        c.drawString(30 + df.columns.get_loc(col) * col_width, y, col)

    # Tabelleninhalt
    y = height - 80
    for index, row in df.iterrows():
        for col in df.columns:
            c.drawString(30 + df.columns.get_loc(col) * col_width, y, str(row[col]))
        y -= row_height
        if y < 40:  # Neue Seite falls nötig
            c.showPage()
            y = height - 40

    c.save()
    buffer.seek(0)
    return buffer

# Hauptlogik der Streamlit-App
def main():
    st.title("Analyse 400m Hürden")

    # Daten laden
    data = load_data()

    # Filteroptionen
    st.sidebar.header("Filteroptionen")
  
    athletes = st.sidebar.multiselect("Athlet wählen", options=data["Name"].unique(), default=data["Name"].unique())
    competitions = st.sidebar.multiselect("Wettkampf wählen", options=data["Wettkampf"].unique(), default=data["Wettkampf"].unique())
    #years = st.sidebar.multiselect("Jahr wählen", options=data["Jahr"].unique(), default=data["Jahr"].unique())
    min_time = st.sidebar.slider("Minimale Zeit (Sekunden)", min_value=float(data["Zeit"].min()), max_value=float(data["Zeit"].max()), value=float(data["Zeit"].min()))
    max_time = st.sidebar.slider("Maximale Zeit (Sekunden)", min_value=float(data["Zeit"].min()), max_value=float(data["Zeit"].max()), value=float(data["Zeit"].max()))

    # Daten filtern
    filtered_data = data[
        (data["Name"].isin(athletes)) & 
        (data["Wettkampf"].isin(competitions)) & 
        #(data["Jahr"].isin(years)) & 
        (data["Zeit"] >= min_time) & 
        (data["Zeit"] <= max_time)
    ]

    st.dataframe(filtered_data)

    # Exportoptionen
    st.header("Exportieren")
    export_format = st.selectbox("Exportformat wählen", ["CSV", "Excel", "PDF"])

    if st.button("Exportieren"):
        if export_format == "CSV":
            csv_data = filtered_data.to_csv(index=False).encode('utf-8')
            st.download_button(label="Download CSV", data=csv_data, file_name="filtered_data.csv", mime="text/csv")
        elif export_format == "Excel":
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                filtered_data.to_excel(writer, index=False, sheet_name='Sheet1')
            st.download_button(label="Download Excel", data=excel_buffer.getvalue(), file_name="filtered_data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif export_format == "PDF":
            pdf_data = to_pdf(filtered_data)
            st.download_button(label="Download PDF", data=pdf_data, file_name="filtered_data.pdf", mime="application/pdf")

if __name__ == "__main__":
    main()