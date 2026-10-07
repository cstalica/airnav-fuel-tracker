import pandas as pd
from playwright.sync_api import sync_playwright
import streamlit as st


@st.cache_data(ttl=3600)
def fetch_live_argus_jet_fuel_index():
    """Renders the Airlines for America page in headless Chromium and extracts

    ALL live chart data points directly from JavaScript memory. Strictly no
    fallbacks.
    """
    url = "https://www.airlines.org/dataset/argus-us-jet-fuel-index/#jet-fuel-prices"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set viewport large enough to capture the full Highcharts canvas
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        # Navigate to page and wait for full JavaScript execution
        page.goto(url, wait_until="networkidle", timeout=15000)

        # Evaluate Highcharts object in the global JS scope across main frame and iframes
        chart_data = page.evaluate("""
            () => {
                // Function to extract from Highcharts instance
                function extractData(win) {
                    if (win.Highcharts && win.Highcharts.charts) {
                        const chart = win.Highcharts.charts.find(c => c !== undefined);
                        if (chart && chart.series && chart.series[0]) {
                            const categories = chart.xAxis[0].categories || [];
                            const seriesData = chart.series[0].yData || [];
                            return categories.map((cat, i) => ({
                                Date: cat,
                                Price: parseFloat(seriesData[i])
                            }));
                        }
                    }
                    return null;
                }

                // 1. Try main window
                let result = extractData(window);
                if (result && result.length > 0) return result;

                // 2. Try embedded child iframes
                for (let i = 0; i < window.frames.length; i++) {
                    try {
                        result = extractData(window.frames[i]);
                        if (result && result.length > 0) return result;
                    } catch (e) {}
                }
                return null;
            }
        """)

        browser.close()

        if not chart_data:
            raise RuntimeError(
                "Could not extract live chart data. JavaScript chart object not found in DOM."
            )

        return chart_data


# --- Streamlit Layout ---
st.title("✈️ Jet A Fuel Tracker (Live Data Only)")

try:
    live_data = fetch_live_argus_jet_fuel_index()

    df = pd.DataFrame(live_data)
    st.success(f"Fetched {len(df)} live data points successfully!")

    # Display full dynamic chart
    st.line_chart(df, x="Date", y="Price")

    # Display underlying table
    st.dataframe(df, use_container_width=True)

except Exception as err:
    st.error(f"Live data extraction failed: {err}")