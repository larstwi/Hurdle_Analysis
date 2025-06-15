import streamlit as st
import pandas as pd
import altair as alt

# Funktion zum Laden der Daten
@st.cache_data
def load_data():
    data = pd.read_excel('data/Analyse13.xlsx')
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
    #competitions = st.sidebar.multiselect("Wettkampf wählen", options=data["Wettkampf"].unique(), default=data["Wettkampf"].unique())
    years = st.sidebar.multiselect("Jahr wählen", options=data["Jahr"].unique(), default=data["Jahr"].unique())
    # Min and Max time input fields (instead of sliders)
    try:
        min_time_input = st.sidebar.text_input("Minimale Zeit (Sekunden)", value=str(float(data["Zeit"].min())))
        min_time = float(min_time_input) if min_time_input else float(data["Zeit"].min())
    except ValueError:
        st.sidebar.error("Bitte eine gültige Zahl für die minimale Zeit eingeben.")
        min_time = float(data["Zeit"].min())  # Default value in case of invalid input
    
    try:
        max_time_input = st.sidebar.text_input("Maximale Zeit (Sekunden)", value=str(float(data["Zeit"].max())))
        max_time = float(max_time_input) if max_time_input else float(data["Zeit"].max())
    except ValueError:
        st.sidebar.error("Bitte eine gültige Zahl für die maximale Zeit eingeben.")
        max_time = float(data["Zeit"].max())  # Default value in case of invalid input

    # Daten filtern
    filtered_data = data[
        (data["Name"].isin(athletes)) & 
        #(data["Wettkampf"].isin(competitions)) & 
        (data["Jahr"].isin(years)) & 
        (data["Zeit"] >= min_time) & 
        (data["Zeit"] <= max_time)
    ]

    st.dataframe(filtered_data)

    selected_columns = filtered_data.iloc[:, [6, 7, 10, 13, 16, 20, 23, 26, 29, 32]]

    st.title("Interactive Line Chart")

    # Reshape the data to long format (for Altair)
    melted_data = selected_columns.reset_index().melt(id_vars=["index"], var_name="Column", value_name="Value")

    # Create an interactive line chart with Altair
    line_chart = alt.Chart(melted_data).mark_line().encode(
        x='index:O',       # X-axis: Index (column number)
        y='Value:Q',       # Y-axis: Values from columns
        color='Column:N',  # Color lines based on the column name
        tooltip=['Column', 'Value']  # Tooltip to display column name and value
    ).properties(
        title="Line Plot of Column Values"
    ).interactive()  # Make it interactive (zoom, pan, etc.)

    # Display the chart
    st.altair_chart(line_chart, use_container_width=True)




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
