import pandas as pd
import sys

# URL provided by user
url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR2M4kUQ9T-7nXDokWkDk0q41fyqzw0SWYoprdh-hN4XSBZy_O0Xz3kaBIgFQQix9se-qi0cjJucm2E/pub?gid=1796489779&single=true&output=csv"

print(f"Fetching: {url}")
try:
    df = pd.read_csv(url)
    print("\nCOLUMNS FOUND:")
    print(list(df.columns))
    print("\nFIRST 3 ROWS:")
    print(df.head(3))
except Exception as e:
    print(f"Error: {e}")
