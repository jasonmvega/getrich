import os
import urllib.request
import json

def load_env():
    env_path = r"C:\Users\S1746017\Downloads\getrich\.env"
    
    with open(env_path) as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                os.environ[key] = value

load_env()

API_KEY = os.environ.get("GETRICH_API_KEY")
API_SECRET = os.environ.get("GETRICH_API_SECRET")
BASE_URL = os.environ.get("GETRICH_BASE_URL")

# --- Function to send order ---
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

# --- Buy AAPL ---
def buy_apple(qty):
    send_order("AAPL", qty, "buy")

# --- Sell AAPL ---
def sell_apple(qty):
    send_order("AAPL", qty, "sell")


# --- Run ---
if __name__ == "__main__":
    buy_apple(5)   # Buy 1 share
    sell_apple(1)  # Uncomment to sell