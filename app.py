# -------------------------------------------------------------
# AirNav Jet A Search Interface
# -------------------------------------------------------------
st.write("Search Jet A fuel prices on AirNav.")

with st.form("airport_search_form", border=False):
    airport_input = st.text_input(
        "Airport Codes Separated by Commas (ICT, FTY, KIXA):", ""
    )
    submitted = st.form_submit_button(
        "Fetch Prices", type="primary", use_container_width=False
    )

if submitted and airport_input.strip():
    airports = [
        code.strip().upper()
        for code in airport_input.replace(";", ",").split(",")
        if code.strip()
    ]
    all_data = []

    progress_bar = st.progress(0)
    for idx, icao in enumerate(airports):
        st.caption(f"Fetching {icao}...")
        results = scrape_airport_jeta(icao)
        if results:
            all_data.extend(results)
        else:
            all_data.append(
                {
                    "Airport": icao,
                    "FBO Name": "N/A or Error",
                    "FBO Link": "",
                    "Jet A Price": "N/A",
                    "Price Updated": "N/A",
                }
            )
        progress_bar.progress((idx + 1) / len(airports))

    if all_data:
        df = pd.DataFrame(all_data)
        st.subheader("Results")
        st.dataframe(
            df,
            column_config={
                "FBO Link": st.column_config.LinkColumn(
                    "FBO Link",
                    display_text="View on AirNav",
                ),
            },
            use_container_width=False,
            hide_index=True,
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📄 Export to CSV",
            data=csv,
            file_name=f"airnav_jeta_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=False,
        )