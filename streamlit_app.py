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

# Function to display differences
def show_row_differences(df, selected_row):
    # Alle numerischen Spalten holen
    numeric_cols = df.select_dtypes(include='number').columns.tolist()

    # Spalte an Position 1 (Index 1) und letzte Spalte ausschließen
    cols_to_exclude = [df.columns[0], df.columns[-1]]
    numeric_cols = [col for col in numeric_cols if col not in cols_to_exclude]

    # Referenzwerte aus gewählter Zeile
    selected_values = df.loc[selected_row, numeric_cols]

    # Differenzen berechnen
    differences = df[numeric_cols].subtract(selected_values, axis=1)

    # Name oder andere Kontextspalte(n) anhängen
    result = pd.concat([df[["Name"]], differences], axis=1)

    # Add context info
    differences["Name"] = df["Name"]
    differences["Wettkampf"] = df["Wettkampf"]

    return result

# Hauptlogik der Streamlit-App
def main():
    st.title("Analyse 400m Hürden")

    # Daten laden
    data = load_data()

    # Filteroptionen
    st.sidebar.header("Filteroptionen")
  
    athletes = st.sidebar.multiselect("Athlet:in wählen", options=data["Name"].unique(), default=data["Name"].unique())
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

    # Show selectable table
    st.subheader("Datenübersicht (zum Vergleich eine Zeile auswählen)")

    # Add a checkbox column for selection
    data_with_selection = filtered_data.copy()
    data_with_selection.insert(0, "Auswählen", False)

    # Use st.data_editor to allow selection
    selected_data = st.data_editor(
        data_with_selection,
        num_rows="dynamic",
        use_container_width=True,
        key="row_selector",
    )

    # Check which row is selected
    selected_indices = selected_data[selected_data["Auswählen"]].index.tolist()

    if len(selected_indices) == 1:
        selected_row = selected_indices[0]
        selected_name = filtered_data.loc[selected_row, "Name"]
        selected_wettkampf = filtered_data.loc[selected_row, "Wettkampf"]
        
        st.markdown(f"### Differenzen relativ zu: {selected_name} - {selected_wettkampf}")
        differences = show_row_differences(filtered_data, selected_row)
        st.dataframe(differences)
    elif len(selected_indices) > 1:
        st.warning("Bitte nur eine Zeile auswählen.")
    else:
        st.info("Wähle eine Zeile aus, um die Differenzen anzuzeigen.")

    #Prepare for charting
    diff_columns = differences.select_dtypes(include='number').columns.drop(['Name', 'Wettkampf'], errors='ignore')
    differences_long = differences.melt(
        id_vars=["Name", "Wettkampf"],
        value_vars=diff_columns,
        var_name="Abschnitt",
        value_name="Differenz"
    )

    # Maintain section order
    differences_long['Abschnitt'] = pd.Categorical(differences_long['Abschnitt'], categories=diff_columns, ordered=False)

    # Line chart of differences
    diff_chart = alt.Chart(differences_long).mark_line().encode(
        x=alt.X("Abschnitt:O", sort=diff_columns),
        y=alt.Y("Differenz:Q"),
        color="Name:N",
        tooltip=["Name", "Wettkampf", "Abschnitt", "Differenz"]
    ).properties(
        title=f"Abschnittsunterschiede zu {label}"
    ).interactive()

    st.altair_chart(diff_chart, use_container_width=True)
    
    selected_columns = filtered_data.iloc[:, [4, 5, 8, 11, 14, 18, 21, 24, 27, 30, 33]]

    # Create a new column 'index' representing the row index
    selected_columns['Wettkampf'] = filtered_data["Name"] + " - " + filtered_data["Wettkampf"]

   # Get the column names (excluding 'index')
    columns_order = selected_columns.columns[:-1].tolist()

    # Melt the data to long format while keeping the columns order intact
    melted_data = selected_columns.melt(id_vars=["Wettkampf"], var_name="Abschnitt", value_name="Abschnittszeit")

    # Ensure the 'Variable' column respects the original order of the columns
    melted_data['Abschnitt'] = pd.Categorical(melted_data['Abschnitt'], categories=columns_order, ordered=False)

    # Now create the line chart (one line per row, each row is a separate line)
    line_chart = alt.Chart(melted_data).mark_line().encode(
        x=alt.X('Abschnitt:O', sort=columns_order),  # Ensure correct column order
        y='Abschnittszeit:Q',  # Y-axis: Values of the row across all columns
        color='Wettkampf:N',  # Color by the row index (each row as a separate line)
        tooltip=['Wettkampf', 'Abschnitt', 'Abschnittszeit']  # Tooltip shows the row index, column, and value
    ).properties(
        title="Abschnittszeiten"
    ).interactive()  # Make it interactive (zoom, pan, etc.)

    # Display the chart
    st.altair_chart(line_chart, use_container_width=True)

    # Exportoptionen
    st.header("Exportieren")
    export_format = st.selectbox("Exportformat wählen", ["CSV"])
    #export_format = st.selectbox("Exportformat wählen", ["CSV", "Excel", "PDF"])

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
