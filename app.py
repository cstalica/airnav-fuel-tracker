import requests
import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600)
def fetch_live_argus_jet_fuel_index():
    """Fetches ONLY live data from the underlying WordPress/Argus API endpoint.

    Raises an error if the live fetch fails instead of using fallback data.
    """
    # Direct endpoint powering the Highcharts graph
    api_url = (
        "https://www.airlines.org/wp-json/a4a/v1/jet-fuel-index"  # API Endpoint
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }

    response = requests.get(api_url, headers=headers, timeout=10)
    response.raise_for_status()  # Force error if live endpoint fails

    data = response.json()
    parsed_data = []

    # Case A: JSON returns standard dict with categories (dates) and series (prices)
    if isinstance(data, dict):
        categories = data.get("categories", [])
        series = data.get("series", [{}])[0].get("data", [])
        if categories and series:
            for dt, price in zip(categories, series):
                parsed_data.append({"Date": str(dt), "Price": float(price)})

    # Case B: JSON returns raw array of records
    elif isinstance(data, list):
        for item in data:
            if "date" in item and "price" in item:
                parsed_data.append(
                    {"Date": str(item["date"]), "Price": float(item["price"])}
                )

    if not parsed_data:
        raise ValueError("Live API response contained no valid data points.")

    return parsed_data