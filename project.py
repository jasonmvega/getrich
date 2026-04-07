import os
import urllib.request
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --- Load ENV ---
env_path = Path(r"C:\Users\S1746017\Downloads\getrich\.env")
with env_path.open() as f:
    for line in f:
        if "=" in line:
            key, value = line.strip().split("=", 1)
            os.environ[key] = value

# --- Get URLs from ENV ---
BASE_URL = os.environ.get("GETRICH_BASE_URL")
DATA_URL = os.environ.get("GETRICH_DATA_URL")

# Verify environment variables
if not BASE_URL or not DATA_URL:
    raise ValueError("BASE_URL or DATA_URL not set in .env")
print("BASE_URL =", BASE_URL)
print("DATA_URL =", DATA_URL)

API_KEY = os.environ.get("GETRICH_API_KEY")
API_SECRET = os.environ.get("GETRICH_API_SECRET")

# --- Get historical prices ---
def get_historical_prices(symbol, limit=300):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=10)

    url = (f"{DATA_URL}/v2/stocks/{symbol}/bars?"
           f"timeframe=1Min&start={start.isoformat()}&end={end.isoformat()}&limit={limit}")

    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        bars = data.get("bars", [])
        return [bar["c"] for bar in bars]  # closing prices

# --- Get latest price ---
def get_price(symbol):
    url = DATA_URL + f"/v2/stocks/{symbol}/quotes/latest"
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        return data["quote"]["ap"]

# --- Get current position ---
def get_position(symbol):
    url = BASE_URL + f"/v2/positions/{symbol}"
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            qty = int(float(data["qty"]))
            avg_price = float(data["avg_entry_price"])
            return qty, avg_price
    except urllib.error.HTTPError:
        return 0, None  # no position exists

# --- Send order ---
def send_order(symbol, qty, side):
    url = BASE_URL + "/v2/orders"
    data = json.dumps({
        "symbol": symbol,
        "qty": qty,
        "side": side,
        "type": "market",
        "time_in_force": "gtc"
    }).encode("utf-8")

    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            result = response.read().decode()
            print(f"{side.upper()} order success:")
            print(result)
    except Exception as e:
        print(f"Error placing {side} order:")
        print(e)

# --- Helper ---
def average(lst):
    return sum(lst) / len(lst)

# --- Trading Logic ---
def trade(symbol, prices_list):
    shares_held, buy_price = get_position(symbol)
    print(f"Current position: {shares_held} shares @ {buy_price}")

    if len(prices_list) < 250:
        print("Not enough data to trade")
        return

    current_price = prices_list[-1]

    # --- SELL ASAP (10% gain) ---
    if shares_held > 0 and buy_price is not None:
        if current_price >= buy_price * 1.10:
            print("SELL ASAP triggered (10% gain)")
            send_order(symbol, shares_held, "sell")
            return

    # --- Moving averages ---
    short_ma = average(prices_list[-50:])
    long_ma  = average(prices_list[-250:])
    prev_short = average(prices_list[-51:-1])
    prev_long  = average(prices_list[-251:-1])

    # --- BUY ---
    if prev_short <= prev_long and short_ma > long_ma and shares_held == 0:
        print("BUY signal (golden cross)")
        send_order(symbol, 100, "buy")

    # --- SELL ---
    elif prev_short >= prev_long and short_ma < long_ma and shares_held > 0:
        print("SELL signal (death cross)")
        send_order(symbol, shares_held, "sell")

    # --- Weak trend ---
    elif prev_long > long_ma:
        print("Weak trend → small BUY (5 shares)")
        send_order(symbol, 5, "buy")

    else:
        print("No action taken")

# --- RUN ONCE ---
if __name__ == "__main__":
    SYMBOL = "AAPL"
    try:
        prices = get_historical_prices(SYMBOL)
        latest_price = get_price(SYMBOL)
        prices.append(latest_price)

        print(f"Latest price: {latest_price}")
        print(f"Loaded {len(prices)} prices")

        trade(SYMBOL, prices)
    except Exception as e:
        print("Error:", e)