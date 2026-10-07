@st.cache_data(ttl=3600)
def fetch_argus_jet_fuel_index():
    """Fetches the 10 most recent spot prices directly from the Argus US Jet Fuel Index

    by parsing the Highcharts data embedded in the Airlines for America page.
    """
    url = "https://www.airlines.org/dataset/argus-us-jet-fuel-index/#jet-fuel-prices"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")
            parsed_data = []

            # 1. Look for Highcharts categories and data series in script tags
            scripts = soup.find_all("script")
            categories = []
            series_data = []

            for script in scripts:
                if not script.string:
                    continue

                # Match categories array e.g., categories: ['10-Jul', '14-Jul', ...]
                cat_match = re.search(
                    r"categories\s*:\s*(\[[^\]]+\])", script.string
                )
                if cat_match:
                    try:
                        categories = json.loads(
                            cat_match.group(1).replace("'", '"')
                        )
                    except Exception:
                        pass

                # Match series data array e.g., data: [3.12, 3.40, ...] or [{y: 3.12}, ...]
                data_match = re.search(
                    r"data\s*:\s*(\[\s*(?:[\d\.]+|\{[\s\S]*?\}|\s*,\s*)*\])",
                    script.string,
                )
                if data_match:
                    try:
                        raw_data = data_match.group(1)
                        # Extract raw numbers or y-values from data objects
                        numbers = re.findall(
                            r"(?:y\s*:\s*)?(\d+\.\d{2})", raw_data
                        )
                        if numbers:
                            series_data = [float(n) for n in numbers]
                    except Exception:
                        pass

                if categories and series_data:
                    break

            # Combine categories (dates) and series values (prices)
            if categories and series_data:
                min_len = min(len(categories), len(series_data))
                for i in range(min_len):
                    parsed_data.append(
                        {"Date": categories[i], "Price": series_data[i]}
                    )

            # 2. Fallback: Parse Highcharts point tuples [timestamp, price] or ['Date', price]
            if not parsed_data:
                for script in scripts:
                    if not script.string:
                        continue
                    matches = re.findall(
                        r"\[\s*[\"']?(\d{1,2}-[A-Za-z]{3})[\"']?\s*,\s*(\d+\.\d+)\s*\]",
                        script.string,
                    )
                    if matches:
                        for dt_str, price_str in matches:
                            parsed_data.append(
                                {"Date": dt_str, "Price": float(price_str)}
                            )
                        break

            # 3. Fallback: Parse Highcharts x-axis labels directly from chart container HTML
            if not parsed_data:
                all_text = soup.get_text()
                dates = re.findall(r"\b\d{1,2}-[A-Za-z]{3}\b", all_text)
                prices = re.findall(r"\$(\d+\.\d{2})", all_text)

                if dates and len(prices) > 1:
                    # Ignore the banner header price ($4.49)
                    chart_prices = [float(p) for p in prices if p != "4.49"]
                    min_len = min(len(dates), len(chart_prices))
                    for i in range(min_len):
                        parsed_data.append(
                            {"Date": dates[i], "Price": chart_prices[i]}
                        )

            if parsed_data:
                return parsed_data[-10:]

    except Exception:
        pass

    return []