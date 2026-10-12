import csv
from datetime import datetime
import yfinance as yf

def capture_price():
    try:
        print("Fetching NY Harbor ULSD price from Yahoo Finance (HO=F)...")
        
        # Pull NY Harbor ULSD Futures ticker data
        ticker = yf.Ticker("HO=F")
        todays_data = ticker.history(period="1d")
        
        if not todays_data.empty:
            # Extract the latest closing/current price
            clean_price = float(todays_data['Close'].iloc[-1])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Append to your local CSV history file
            with open("ulsd_history.csv", mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, clean_price])
                
            print(f"SUCCESS: Captured NY Harbor ULSD price ${clean_price:.4f} at {timestamp}")
        else:
            print("ERROR: No data returned from Yahoo Finance.")
            raise ValueError("Empty data returned.")
            
    except Exception as e:
        print(f"Scraper failed: {e}")
        raise e

if __name__ == "__main__":
    capture_price()