from datetime import datetime
import json
import re
import altair as alt
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

# Centered Layout Page Config
st.set_page_config(
    page_title="Jet A Fuel Tracker",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


@st.cache_data(ttl=3600)
def fetch_live_argus_jet_fuel_index():
    """Fetches the live 60-day spot price series from Airlines for America."""
    url = "https://www.airlines.org/dataset/argus-us-jet-fuel-index/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    parsed_data = []

    try:
        session = requests.Session()
        res = session.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")

            # Check for embedded iframe or highcharts script tags
            iframe = soup.find("iframe")
            target_content = res.text

            if iframe and iframe.get("src"):
                iframe_url = iframe["src"]
                if not iframe_url.startswith("http"):
                    iframe_url = "https://www.airlines.org" + iframe_url
                iframe_res = session.get(iframe_url, headers=headers, timeout=10)
                if iframe_res.status_code == 200:
                    target_content = iframe_res.text

            # Parse categories (dates) and series data (prices) from Highcharts script
            cat_match = re.search(
                r"categories\s*:\s*(\[[^\]]+\])", target_content
            )
            data_match = re.search(
                r"data\s*:\s*(\[\s*(?:[\d\.]+|\{[\s\S]*?\}|\s*,\s*)*\])",
                target_content,
            )

            if cat_match and data_match:
                raw_cats = cat_match.group(1).replace("'", '"')
                categories = json.loads(raw_cats)

                prices = [
                    float(p)
                    for p in re.findall(r"\b\d+\.\d{2}\b", data_match.group(1))
                ]

                min_len = min(len(categories), len(prices))
                for i in range(min_len):
                    parsed_data.append(
                        {"Date": str(categories[i]), "Price": prices[i]}
                    )

    except Exception as e:
        st.error(f"Error fetching live data: {e}")

    return parsed_data


# Streamlit Layout & Display
st.title("✈️ Jet A Fuel Tracker")

latest_index_data = fetch_live_argus_jet_fuel_index()

if latest_index_data:
    st.markdown("### 📊 Argus US Jet Fuel Index")
    df_index = pd.DataFrame(latest_index_data)
    df_index["Price_Label"] = df_index["Price"].apply(lambda x: f"${x:.2f}")

    min_price = df_index["Price"].min()
    max_price = df_index["Price"].max()
    padding = max(0.05, (max_price - min_price) * 0.2)

    chart = (
        alt.Chart(df_index)
        .mark_line(point=True, color="#1f77b4", strokeWidth=2.5)
        .encode(
            x=alt.X("Date:N", sort=None, title="Date"),
            y=alt.Y(
                "Price:Q",
                scale=alt.Scale(domain=[min_price - padding, max_price + padding]),
                title="Price ($/gal)",
            ),
            tooltip=["Date", "Price_Label"],
        )
        .properties(height=380)
    )

    st.altair_chart(chart, use_container_width=True)
    st.dataframe(df_index, use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ Live Jet Fuel Index data could not be parsed from the page.")