import pandas as pd
import requests
import io

def get_jet_fuel_index():
    # Direct link to the EIA Spot Prices Excel file
    url = "https://www.eia.gov/dnav/pet/xls/PET_PRI_SPT_S1_D.xls"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Read the file directly into memory. 
        # 'Data 6' sheet typically holds the Gulf Coast Kerosene-Type Jet Fuel data.
        df = pd.read_excel(io.BytesIO(response.content), sheet_name='Data 6', header=2)
        
        # Clean the data and grab the last available row
        df = df.dropna()
        latest_row = df.iloc[-1]
        
        latest_date = latest_row.iloc[0].strftime('%Y-%m-%d')
        latest_price = float(latest_row.iloc[1])
        
        return {"date": latest_date, "price": latest_price}
        
    except Exception as e:
        print(f"Failed to fetch Jet Fuel Data: {e}")
        return None