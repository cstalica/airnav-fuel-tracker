import csv
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

def capture_price():
    # The actual CME Group NY Harbor ULSD URL
    url = "https://www.cmegroup.com/markets/energy/refined-products/heating-oil.html"
    
    print(f"Connecting to {url}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        try:
            # Navigate to the real CME page and wait for network activity to settle
            page.goto(url, timeout=60000, wait_until="networkidle")
            
            html_content = page.content()
            
            # Regex targeting the "LAST" label and capturing the immediately following price (e.g., 4.6944)
            match = re.search(r"LAST.*?([0-9]+\.[0-9]{2,4})", html_content, re.DOTALL | re.IGNORECASE)
            
            if match:
                clean_price = float(match.group(1))
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                with open("ulsd_history.csv", mode="a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, clean_price])
                    
                print(f"SUCCESS: Captured price ${clean_price} at {timestamp}")
            else:
                print("ERROR: Price pattern not found in page content.")
                raise ValueError("Could not extract price via regex.")
                
        except Exception as e:
            print(f"Scraper failed: {e}")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    capture_price()