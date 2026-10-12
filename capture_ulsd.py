import csv
from datetime import datetime
from playwright.sync_api import sync_playwright

def capture_price():
    # Use the actual CME Group Heating Oil / NY Harbor ULSD URL
    url = "https://www.cmegroup.com/markets/energy/refined-products/heating-oil.html"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Set a standard desktop user agent to prevent bot blocks
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        
        try:
            page.goto(url, timeout=60000)
            
            # Wait for the LAST price label to appear on the page
            page.wait_for_selector("text=LAST", timeout=20000)
            
            # Locate the text value immediately following the LAST label (e.g., 4.6967)
            price_elem = page.locator("xpath=//*[contains(text(), 'LAST')]/following-sibling::*[1]").first
            price_text = price_elem.inner_text().strip()
            
            clean_price = float(price_text.replace("$", "").replace(",", ""))
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open("ulsd_history.csv", mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, clean_price])
                print(f"Successfully captured price: {clean_price} at {timestamp}")
                
        except Exception as e:
            print(f"Failed to extract price: {e}")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    capture_price()