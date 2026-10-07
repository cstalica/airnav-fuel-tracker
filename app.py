import json
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
    target = soup.