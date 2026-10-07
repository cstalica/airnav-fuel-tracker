@st.cache_data(ttl=3600)
def fetch_argus_jet_fuel_index():
    """Fetches the 10 most recent spot prices directly from the Argus US Jet Fuel Index
    without manual fallback prices.
    """
    url = "https://www.airlines.org/dataset/argus-us-jet-fuel-index/#jet-fuel-prices"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")
            parsed_data = []

            # 1. Inspect embedded JSON scripts for Highcharts series
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "series" in script.string:
                    # Match highcharts series data arrays
                    matches = re.findall(r"\[\s*(?:['\"](\d{1,2}-[A-Za-z]{3})['\"]|\d+)\s*,\s*(\d+\.\d+)\s*\]", script.string)
                    if matches:
                        for dt_str, price_str in matches:
                            parsed_data.append({"Date": dt_str, "Price": float(price_str)})
                        break

            # 2. Extract from page text or embedded Highcharts category lists if script parsing yielded no data
            if not parsed_data:
                # Extract date labels (e.g., 10-Jul, 14-Jul, 06-Oct) and numeric prices
                dates = re.findall(r"\b\d{1,2}-[A-Za-z]{3}\b", soup.get_text())
                prices = re.findall(r"\$(\d+\.\d{2})", soup.get_text())
                
                # Pair matched items if lengths align
                if dates and prices:
                    min_len = min(len(dates), len(prices))
                    for i in range(min_len):
                        parsed_data.append({"Date": dates[i], "Price": float(prices[i])})

            if parsed_data:
                return parsed_data[-10:]

    except Exception:
        pass

    return []