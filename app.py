import io
import re
from datetime import datetime
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


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_eia_jet_fuel_excel():
    """
    Live extraction from U.S. Energy Information Administration (EIA) daily Excel file.
    This bypasses Cloudflare/Akamai blocks by targeting the static file server directly.
    """
    url = "https://www.eia.gov/dnav/pet/xls/PET_PRI_SPT_S1_D.xls"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # Read the file directly into memory. 'Data 6' contains Jet Fuel Spot Prices.
        # header=2 skips the EIA title rows so the columns align properly.
        df = pd.read_excel(io.BytesIO(response.content), sheet_name='Data 6', header=2)
        
        # Rename columns to standard names
        df.columns = ["RawDate", "Price"]
        df = df.dropna()

        # Grab the last 10 available rows (chronological order)
        df_last_10 = df.tail(10).copy()

        parsed_data = []
        for _, row in df_last_10.iterrows():
            # Format the date as DD-Mon (e.g., 04-Oct) for the chart
            dt_obj = pd.to_datetime(row["RawDate"])
            parsed_data.append({
                "Date": dt_obj.strftime("%d-%b"),
                "Price": float(row["Price"])
            })

        if parsed_data:
            return parsed_data

    except Exception as e:
        print(f"Excel parsing error: {e}")
        pass

    # Raise an exception so Streamlit DOES NOT cache a failure state
    raise RuntimeError("Failed to fetch live Jet Fuel Data from EIA Excel source.")


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

    fs_price, ss_price, as_price = None, None, None

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

    price = fs_price or ss_price or as_price

    if price:
        try:
            clean_val = re.sub(r"[^\d.]", "", price)
            price = f"${float(clean_val):.2f}"
        except ValueError:
            pass

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
        "more info", "website", "web site", "email", "guaranteed", "read",
        "write", "photos", "asri", "tel:", "fax:", "hertz", "go rentals",
        "enterprise", "national", "caa", "nata", "airboss", "reserve",
        "multi service", "click here",
    ]

    fbo_links = target_elem.find_all("a", href=re.compile(r"/fbo/", re.IGNORECASE))
    for a_tag in fbo_links:
        text = a_tag.get_text(strip=True) or (
            a_tag.find("img").get("alt", "") if a_tag.find("img") else ""
        )
        cleaned = clean_name(text)
        if cleaned and len(cleaned) > 2 and not any(kw in cleaned.lower() for kw in ignore_keywords):
            href = a_tag.get("href", "")
            full_url = f"https://www.airnav.com{href}" if href.startswith("/") else href
            return cleaned, full_url

    for a_tag in target_elem.find_all("a"):
        text = a_tag.get_text(strip=True) or (
            a_tag.find("img").get("alt", "") if a_tag.find("img") else ""
        )
        cleaned = clean_name(text)
        if cleaned and len(cleaned) > 2 and not any(kw in cleaned.lower() for kw in ignore_keywords):
            href = a_tag.get("href", "")
            full_url = f"https://www.airnav.com{href}" if href.startswith("/") else href
            return cleaned, full_url

    for b_tag in target_elem.find_all(["b", "strong"]):
        cleaned = clean_name(b_tag.get_text(strip=True))
        if cleaned and len(cleaned) > 2 and not any(kw in cleaned.lower() for kw in ignore_keywords):
            return cleaned, None

    for img in target_elem.find_all("img"):
        cleaned = clean_name(img.get("alt", "") or img.get("title", ""))
        if cleaned and len(cleaned) > 2 and not any(
            kw in cleaned.lower() for kw in ignore_keywords + ["phillips", "independent", "world fuel"]
        ):
            return cleaned, None

    lines = [
        line.strip()
        for line in target_elem.get_text(separator="\n").split("\n")
        if line.strip()
    ]
    for line in lines:
        cleaned = clean_name(line)
        if cleaned and len(cleaned) > 2 and not any(kw in cleaned.lower() for kw in ignore_keywords):
            return cleaned, None

    return "Unknown FBO", None


def strip_nearby_airports_section(soup):
    target = soup.find(
        string=re.compile(r"Alternatives at nearby airports|Nearby airports", re.IGNORECASE)
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
            for kw in ["alternatives at nearby airports", "nearby airports", "located at"]
        ):
            continue
        if "Jet A" in table_text and any(x in table_text for x in ["FS", "SS", "AS"]):
            fbo_container = table.find_parent("tr")
            if fbo_container and "located at" in fbo_container.get_text().lower():
                continue
            price, updated_date = parse_fbo_fuel_table(table)
            if price:
                fbo_name, fbo_url = get_fbo_name(fbo_container)
                fbo_results.append({
                    "Airport": icao,
                    "FBO Name": fbo_name,
                    "FBO Link": fbo_url if fbo_url else "",
                    "Jet A Price": price,
                    "Price Updated": updated_date,
                })
    return fbo_results


# Main UI Layout
st.title("✈️ Jet A Fuel Tracker")

# AirNav Search Section
st.write("Search Jet A fuel prices on AirNav.")

with st.form("airport_search_form", border=False):
    airport_input = st.text_input("Airport Codes Separated by Commas (ICT, FTY):", "")
    submitted = st.form_submit_button("Fetch Prices", type="primary")

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
            all_data.append({
                "Airport": icao,
                "FBO Name": "N/A or Error",
                "FBO Link": "",
                "Jet A Price": "N/A",
                "Price Updated": "N/A",
            })
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
            hide_index=True,
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📄 Export to CSV",
            data=csv,
            file_name=f"airnav_jeta_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

st.divider()

# Jet Fuel Index Section
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("### 📊 EIA Jet Fuel Spot Price Index")
with col2:
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

try:
    latest_index_data = fetch_eia_jet_fuel_excel()
except Exception:
    latest_index_data = []

if latest_index_data:
    df_index = pd.DataFrame(latest_index_data)
    df_index["Price_Label"] = df_index["Price"].apply(lambda x: f"${x:.2f}")

    min_price = df_index["Price"].min()
    max_price = df_index["Price"].max()
    padding = max(0.05, (max_price - min_price) * 0.25)
    y_min = round(min_price - padding, 2)
    y_max = round(max_price + padding, 2)

    base = alt.Chart(df_index).encode(
        x=alt.X("Date:N", sort=None, axis=alt.Axis(title="Date", titleFontWeight="bold", labelFontWeight="bold")),
        y=alt.Y("Price:Q", scale=alt.Scale(domain=[y_min, y_max]), axis=alt.Axis(title="Price ($/gal)", titleFontWeight="bold", labelFontWeight="bold")),
    )

    line_layer = base.mark_line(color="#1f77b4", strokeWidth=3)
    point_layer = base.mark_point(color="#1f77b4", size=60, filled=True)
    text_layer = base.mark_text(
        align="center", baseline="bottom", dy=-10, fontSize=12, fontWeight="bold"
    ).encode(
        text="Price_Label:N",
        color=alt.value("white"),
    )

    chart = (line_layer + point_layer + text_layer).properties(height=350).configure_axis(grid=True)
    st.altair_chart(chart, use_container_width=True)
else:
    st.warning("⚠️ Live Jet Fuel Index data is currently unavailable. Click 'Refresh Data' above to try again.")