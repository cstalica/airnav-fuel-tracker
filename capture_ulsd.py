import csv
from datetime import datetime
from playwright.sync_api import sync_playwright

def capture_price():
    url = "https://www.cmegroup.com/markets/energy/refined-products/heating-oil.html"
    
    with sync_playwright() as p:
        # Launch headless browser to render JavaScript elements
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        
        try:
            # Wait for the last price element to load in the DOM
            # (Adjust selector based on exact DOM structure)
            price_elem = page.locator("text=LAST").locator("xpath=following-sibling::*").first
            price_text = price_elem.inner_text().strip()
            
            clean_price = float(price_text.replace("$", "").replace(",", ""))
            timestamp = datetime.now().strftime("%Y-%m-%d 17:00:00")
            
            # Append to your CSV file
            with open("ulsd_history.csv", mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, clean_price])
                
        except Exception as e:
            print(f"Failed to extract price: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    capture_price()