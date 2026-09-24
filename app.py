from datetime import datetime
import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import streamlit as st

# Mobile-Optimized Page Config
st.set_page_config(
    page_title="Jet A Fuel Tracker",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def fetch_eia_ulsd_spot_prices():
    """Fetches NY Harbor ULSD spot prices from EIA and computes weekly averages."""
    url = "https://www.eia.gov/dnav/pet/hist/eer_epd2dxl0_pf4_y35ny_dpgD.htm"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return pd.DataFrame()

        soup = BeautifulSoup(res.content, "html.parser")
        
        # Locate the table containing the spot price data
        table = None
        for t in soup.find_all("table"):
            if "Week Of" in t.get_text():
                table = t
                break

        if not table:
            return pd.DataFrame()

        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) >= 6 and "to" in cells[0]:
                week_of = cells[0]
                daily_prices = []
                for val in cells[1:6]:
                    try:
                        daily_prices.append(float(val))
                    except ValueError:
                        daily_prices.append(None)

                # Ensure 5 daily price columns
                while len(daily_prices) < 5:
                    daily_prices.append(None)

                # Compute average ignoring missing/holiday days
                valid_prices = [p for p in daily_prices if p is not None]
                weekly_avg = sum(valid_prices) / len(valid_prices) if valid_prices else None

                rows.append([week_of] + daily_prices + [weekly_avg])

        df = pd.DataFrame(
            rows,
            columns=["Week Of", "Mon", "Tue", "Wed", "Thu", "Fri", "Weekly Average"]
        )
        return df

    except Exception:
        return pd.DataFrame()


def parse_fbo_fuel_table(fuel_table):
    headers = []
    for tr in fuel_table.find_all("tr"):
        row_text = tr.get_text()
        if "Jet A" in row_text:
            headers = [
                td.get_text(strip=True)
                for td in tr.find_all(["td", "th"])
                if td.get_text(strip=True)
            ]
            break

    if not headers or "Jet A" not in headers:
        return None, "N/A"

    try:
        jeta_col_idx = headers.index("Jet A")
    except ValueError:
        return None, "N/A"

    fs_price = None
    ss_price = None
    as_price = None

    for tr in fuel_table.find_all("tr"):
        cells = [
            td.get_text(strip=True)
            for td in tr.find_all(["td", "th"])
            if td.get_text(strip=True)
        ]
        if not cells:
            continue

        service_type = cells[0].upper()
        price_cells = cells[1:]

        if service_type == "FS" and jeta_col_idx < len(price_cells):
            val = price_cells[jeta_col_idx]
            if val and val != "N/A":
                fs_price = val
        elif service_type == "SS" and jeta_col_idx < len(price_cells):
            val = price_cells[jeta_col_idx]
            if val and val != "N/A":
                ss_price = val
        elif service_type == "AS" and jeta_col_idx < len(price_cells):
            val = price_cells[jeta_col_idx]
            if val and val != "N/A":
                as_price = val

    # Priority order: FS -> SS -> AS
    price = fs_price or ss_price or as_price

    table_text = fuel_table.get_text()
    date_match = re.search(
        r"Updated\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", table_text, re.IGNORECASE
    )
    updated_date = "N/A"
    if date_match:
        raw_date = date_match.group(1)
        try:
            parsed_dt = datetime.strptime(raw_date, "%d-%b-%Y")
            updated_date = parsed_dt.strftime("%m-%d-%Y")
        except ValueError:
            updated_date = raw_date

    return price, updated_date


def get_fbo_name(fbo_container):
    if not fbo_container:
        return "Unknown FBO", None

    tds = fbo_container.find_all("td", recursive=False) or fbo_container.find_all("td")
    target_elem = tds[0] if tds else fbo_container

    def clean_name(raw_text):
        if not raw_text:
            return ""
        cleaned = re.sub(
            r"^(More info and photos of|More info about|More info of|More info|Photos of|Photos)\s*",
            "",
            raw_text,
            flags=re.IGNORECASE,
        ).strip()
        return re.sub(r"\d{3}[-\s]?\d{3}[-\s]?\d{4}.*", "", cleaned).strip()

    ignore_keywords = [
        "more info",
        "website",
        "web site",
        "email",
        "guaranteed",
        "read",
        "write",
        "photos",
        "asri",
        "tel:",
        "fax:",
        "hertz",
        "go rentals",
        "enterprise",
        "national",
        "caa",
        "nata",
        "airboss",
        "reserve",
        "multi service",
        "click here",
    ]

    fbo_links = target_elem.find_all("a", href=re.compile(r"/fbo/", re.IGNORECASE))
    for a_tag in fbo_links:
        text = a_tag.get_text(strip=True) or (
            a_tag.find("img").get("alt", "") if a_tag.find("img") else ""
        )
        cleaned = clean_name(text)
        if (
            cleaned
            and len(cleaned) > 2
            and not any(kw in cleaned.lower() for kw in ignore_keywords)
        ):
            href = a_tag.get("href", "")
            full_url = f"https://www.airnav.com{href}" if href.startswith("/") else href
            return cleaned, full_url

    for a_tag in target_elem.find_all("a"):
        text = a_tag.get_text(strip=True) or (
            a_tag.find("img").get("alt", "") if a_tag.find("img") else ""
        )
        cleaned = clean_name(text)
        if (
            cleaned
            and len(cleaned) > 2
            and not any(kw in cleaned.lower() for kw in ignore_keywords)
        ):
            href = a_tag.get("href", "")
            full_url = f"https://www.airnav.com{href}" if href.startswith("/") else href
            return cleaned, full_url

    for b_tag in target_elem.find_all(["b", "strong"]):
        cleaned = clean_name(b_tag.get_text(strip=True))
        if (
            cleaned
            and len(cleaned) > 2
            and not any(kw in cleaned.lower() for kw in ignore_keywords)
        ):
            return cleaned, None

    for img in target_elem.find_all("img"):
        cleaned = clean_name(img.get("alt", "") or img.get("title", ""))
        if (
            cleaned
            and len(cleaned) > 2
            and not any(
                kw in cleaned.lower()
                for kw in ignore_keywords + ["phillips", "independent", "world fuel"]
            )
        ):
            return cleaned, None

    lines = [
        line.strip()
        for line in target_elem.get_text(separator="\n").split("\n")
        if line.strip()
    ]
    for line in lines:
        cleaned = clean_name(line)
        if (
            cleaned
            and len(cleaned) > 2
            and not any(kw in cleaned.lower() for kw in ignore_keywords)
        ):
            return cleaned, None

    return "Unknown FBO", None


def strip_nearby_airports_section(soup):
    target = soup.find(
        string=re.compile(
            r"Alternatives at nearby airports|Nearby airports", re.IGNORECASE
        )
    )
    if target:
        tr = target.find_parent("tr")
        if tr:
            for sibling in list(tr.find_next_siblings("tr")):
                sibling.decompose()
            tr.decompose()


def scrape_airport_jeta(icao):
    icao = icao.strip().upper()
    url = f"https://www.airnav.com/airport/{icao}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
            " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0"
            " Mobile/15E148 Safari/604.1"
        )
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(res.content, "html.parser")
    strip_nearby_airports_section(soup)

    fbo_results = []
    for table in soup.find_all("table"):
        table_text = table.get_text()
        if any(
            kw in table_text.lower()
            for kw in [
                "alternatives at nearby airports",
                "nearby airports",
                "located at",
            ]
        ):
            continue
        if "Jet A" in table_text and any(x in table_text for x in ["FS", "SS", "AS"]):
            fbo_container = table.find_parent("tr")
            if fbo_container and "located at" in fbo_container.get_text().lower():
                continue
            price, updated_date = parse_fbo_fuel_table(table)
            if price:
                fbo_name, fbo_url = get_fbo_name(fbo_container)
                fbo_results.append(
                    {
                        "Airport": icao,
                        "FBO Name": fbo_name,
                        "FBO Link": fbo_url if fbo_url else "",
                        "Jet A Price": price,
                        "Price Updated": updated_date,
                    }
                )
    return fbo_results


# UI Layout
st.title("✈️ Jet A Fuel Tracker")

# Tab navigation for FBO Search and EIA ULSD Spot Prices
tab1, tab2 = st.tabs(["AirNav Jet A Tracker", "NY Harbor ULSD Spot Prices"])

with tab1:
    st.write("Search Jet A fuel prices on AirNav.")
    airport_input = st.text_input("Airport Codes Separated by Commas (ICT, FTY, KIXA):", "")

    if st.button("Fetch Prices", type="primary", use_container_width=True):
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
                use_container_width=True,
                hide_index=True,
            )

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📄 Export to CSV",
                data=csv,
                file_name=f"airnav_jeta_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

with tab2:
    st.subheader("EIA NY Harbor ULSD Spot Prices")
    st.write("Fetches historical weekly spot prices with a calculated weekly average column.")
    
    if st.button("Fetch EIA Spot Data", use_container_width=True):
        with st.spinner("Fetching EIA Spot Data..."):
            eia_df = fetch_eia_ulsd_spot_prices()
            
        if not eia_df.empty:
            st.dataframe(
                eia_df,
                column_config={
                    "Weekly Average": st.column_config.NumberColumn(format="$%.4f"),
                    "Mon": st.column_config.NumberColumn(format="$%.3f"),
                    "Tue": st.column_config.NumberColumn(format="$%.3f"),
                    "Wed": st.column_config.NumberColumn(format="$%.3f"),
                    "Thu": st.column_config.NumberColumn(format="$%.3f"),
                    "Fri": st.column_config.NumberColumn(format="$%.3f"),
                },
                use_container_width=True,
                hide_index=True,
            )
            
            eia_csv = eia_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📄 Export EIA Data to CSV",
                data=eia_csv,
                file_name=f"eia_ulsd_spot_prices_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.error("Failed to fetch EIA spot price data.")