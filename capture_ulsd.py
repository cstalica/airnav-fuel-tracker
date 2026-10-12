import csv
from datetime import datetime
from playwright.sync_api import sync_playwright

def capture_price():
    url = "https://www.cmegroup.com/markets/energy/refined-products/heating-oil.html"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        
        try:
            # Wait for the LAST price span/value to render
            page.wait_for_selector("text=LAST", timeout=15000)
            
            # Extract the live price text adjacent to the Last label
            price_elem = page.locator("xpath=//*[contains(text(), 'LAST')]/following-sibling::*[1]").first
            price_text = price_elem.inner_text().strip()
            
            clean_price = float(price_text.replace("$", "").replace(",", ""))
            # Use current exact timestamp for test logging intervals
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open("ulsd_history.csv", mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, clean_price])
                print(f"Successfully captured price: {clean_price} at {timestamp}")
                
        except Exception as e:
            print(f"Failed to extract price: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    capture_price()