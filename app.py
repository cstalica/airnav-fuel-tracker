from datetime import datetime
import re
import bs4
from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st

# Mobile-Optimized Page Config
st.set_page_config(
    page_title="Jet A Fuel Tracker",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


@st.cache_data(ttl=300)
def fetch_nymex_ulsd():
    """Fetch live NYMEX Ultra-Low-Sulfur Diesel (HO=F) futures price."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/HO=F"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            market_time = meta.get("regularMarketTime")

            if price is not None and market_time is not None:
                formatted_price = f"${price:.2f} / gal"
                dt = datetime.fromtimestamp(market_time)
                formatted_time = dt.strftime("%b %d, %Y at %I:%M %p")
                return formatted_price, formatted_time
    except Exception:
        pass
    return None, None


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

    # Focus specifically on the first TD cell (Business Name column)
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

    # 1. Check for <a> hyperlink tags containing '/fbo/'
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

    # 2. Check for any other <a> tags in the business name cell
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

    # 3. Check for <b> or <strong> tags
    for b_tag in target_elem.find_all(["b", "strong"]):
        cleaned = clean_name(b_tag.get_text(strip=True))
        if (
            cleaned
            and len(cleaned) > 2
            and not any(kw in cleaned.lower() for kw in ignore_keywords)
        ):
            return cleaned, None

    # 4. Check for <img> tags
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

    # 5. Extract plain text line-by-line when business name is plain text
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
st.write("Search Jet A fuel prices on AirNav.")

# NYMEX ULSD Benchmark Card
ulsd_price, ulsd_time = fetch_nymex_ulsd()
if ulsd_price:
    m_col1, m_col2 = st.columns([1, 1])
    with m_col1:
        st.metric(
            label="🛢️ NYMEX ULSD Futures (HO=F)",
            value=ulsd_price,
        )
    with m_col2:
        st.caption(f"**Market Timestamp:**\n\n{ulsd_time}")
    st.divider()

airport_input = st.text_input(
    "Airport Codes Separated by Commas (ICT, FTY, KIXA):", ""
)

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