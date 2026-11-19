
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


# ============================================================
# CONFIGURATION
# ============================================================

SYMBOL = "MSFT"

DATA_FILE = Path("data/msft_2024_5min.csv")

RESULTS_DIR = Path("results")
RESULTS_FILE = RESULTS_DIR / "msft_predictions.csv"
ORDERS_FILE = RESULTS_DIR / "msft_paper_orders.csv"

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

DATA_FEED = os.getenv("ALPACA_DATA_FEED", "iex")

# Fixed paper-trading endpoint. Never use the live endpoint here.
PAPER_URL = "https://paper-api.alpaca.markets"

BASE_URL = "https://data.alpaca.markets/v2/stocks"

FEATURES = [
    "return_1",
    "range_percent"
]

FLAT_THRESHOLD = 0.01

# Paper-trading controls
ENABLE_PAPER_TRADING = (
    os.getenv("ENABLE_PAPER_TRADING", "false").lower() == "true"
)

BUY_AMOUNT = 10.00


# ============================================================
# ALPACA HEADERS
# ============================================================

def alpaca_headers():

    if not API_KEY or not API_SECRET:
        raise ValueError(
            "Missing API_KEY or API_SECRET GitHub secrets."
        )

    return {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
        "Content-Type": "application/json"
    }


# ============================================================
# ALPACA MARKET DATA
# ============================================================

def get_latest_bars():

    headers = alpaca_headers()

    url = f"{BASE_URL}/{SYMBOL}/bars"

    params = {
        "timeframe": "5Min",
        "limit": 1000,
        "feed": DATA_FEED
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    all_bars = data.get("bars", [])

    if not all_bars:
        raise ValueError("Alpaca returned no market bars.")

    df = pd.DataFrame(all_bars)

    df = df.rename(columns={
        "t": "ts_utc",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume"
    })

    df["ts_utc"] = pd.to_datetime(
        df["ts_utc"],
        utc=True
    )

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.sort_values("ts_utc")
    df = df.drop_duplicates(subset="ts_utc")
    df = df.dropna(subset=["high", "low", "close"])
    df = df.reset_index(drop=True)

    return df


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def create_features(df):

    df = df.copy()

    df["return_1"] = (
        df["close"].pct_change(1) * 100
    )

    df["range_percent"] = (
        (df["high"] - df["low"]) /
        df["close"] * 100
    )

    return df


# ============================================================
# LOAD HISTORICAL TRAINING DATA
# ============================================================

def load_training_data():

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Training data not found: {DATA_FILE}"
        )

    df = pd.read_csv(DATA_FILE)

    required = [
        "ts_utc",
        "high",
        "low",
        "close"
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"Training CSV is missing column: {col}"
            )

    df["ts_utc"] = pd.to_datetime(
        df["ts_utc"],
        utc=True
    )

    for col in ["high", "low", "close"]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.sort_values("ts_utc")
    df = df.drop_duplicates(subset="ts_utc")
    df = df.dropna(subset=["high", "low", "close"])
    df = df.reset_index(drop=True)

    df = create_features(df)

    # Three 5-minute bars = 15 minutes
    df["future_close"] = df["close"].shift(-3)
    df["future_ts"] = df["ts_utc"].shift(-3)

    df["target"] = (
        (df["future_close"] - df["close"]) /
        df["close"] * 100
    )

    valid_gap = (
        df["future_ts"] - df["ts_utc"]
        == pd.Timedelta(minutes=15)
    )

    df = df.loc[valid_gap].copy()

    df = df.dropna(
        subset=FEATURES + ["target"]
    )

    if len(df) < 100:
        raise ValueError(
            "Not enough valid historical training observations."
        )

    return df


# ============================================================
# TRAIN LINEAR REGRESSION
# ============================================================

def train_model():

    df = load_training_data()

    X = df[FEATURES]
    y = df["target"]

    model = LinearRegression()
    model.fit(X, y)

    print("\nMODEL TRAINING")
    print("------------------------------")
    print(f"Training observations: {len(df)}")
    print(f"Features: {FEATURES}")
    print(f"Intercept: {model.intercept_:.8f}")

    for feature, coefficient in zip(
        FEATURES,
        model.coef_
    ):
        print(f"{feature}: {coefficient:.8f}")

    training_predictions = model.predict(X)

    print(
        "Training MAE:",
        round(mean_absolute_error(y, training_predictions), 6)
    )

    print(
        "Training RMSE:",
        round(
            np.sqrt(
                mean_squared_error(y, training_predictions)
            ),
            6
        )
    )

    print(
        "Training R²:",
        round(r2_score(y, training_predictions), 6)
    )

    return model


# ============================================================
# GENERATE PREDICTION
# ============================================================

def make_prediction(model):

    bars = get_latest_bars()

    bars = create_features(bars)

    valid_bars = bars.dropna(subset=FEATURES)

    if valid_bars.empty:
        raise ValueError("No valid bars available for prediction.")

    latest = valid_bars.iloc[-1]

    bar_time = latest["ts_utc"]

    now = pd.Timestamp.now(tz="UTC")

    age_minutes = (
        now - bar_time
    ).total_seconds() / 60

    if age_minutes > 30:
        raise ValueError(
            f"Latest bar is stale ({age_minutes:.1f} minutes old)."
        )

    X_latest = pd.DataFrame(
        [latest[FEATURES].to_dict()],
        columns=FEATURES
    )

    predicted_change = float(
        model.predict(X_latest)[0]
    )

    current_close = float(latest["close"])

    predicted_future_price = (
        current_close *
        (1 + predicted_change / 100)
    )

    if predicted_change > FLAT_THRESHOLD:
        direction = "UP"

    elif predicted_change < -FLAT_THRESHOLD:
        direction = "DOWN"

    else:
        direction = "FLAT"

    target_time = bar_time + pd.Timedelta(minutes=15)

    result = {
        "symbol": SYMBOL,
        "prediction_time_utc": now.isoformat(),
        "bar_time_utc": bar_time.isoformat(),
        "target_time_utc": target_time.isoformat(),
        "current_close": current_close,
        "predicted_change_percent": predicted_change,
        "predicted_future_price": predicted_future_price,
        "direction": direction,
        "actual_future_change_percent": np.nan,
        "prediction_error": np.nan
    }

    print("\nPREDICTION")
    print("------------------------------")
    print(f"Direction: {direction}")
    print(f"Predicted change: {predicted_change:.6f}%")
    print(f"Current close: ${current_close:.2f}")
    print(f"Predicted future price: ${predicted_future_price:.2f}")

    return result


# ============================================================
# SAVE PREDICTION
# ============================================================

def save_prediction(result):

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if RESULTS_FILE.exists():

        old_results = pd.read_csv(RESULTS_FILE)

        if "bar_time_utc" in old_results.columns:

            duplicate = old_results[
                "bar_time_utc"
            ].astype(str).eq(result["bar_time_utc"]).any()

            if duplicate:
                print("Prediction already recorded for this bar.")
                return False

        results = pd.concat(
            [old_results, pd.DataFrame([result])],
            ignore_index=True
        )

    else:
        results = pd.DataFrame([result])

    results.to_csv(
        RESULTS_FILE,
        index=False
    )

    print(f"\nPrediction saved to {RESULTS_FILE}")

    return True


# ============================================================
# PAPER ACCOUNT CHECK
# ============================================================

def check_paper_account():

    response = requests.get(
        f"{PAPER_URL}/v2/account",
        headers=alpaca_headers(),
        timeout=30
    )

    response.raise_for_status()

    account = response.json()

    if account.get("trading_blocked"):
        raise RuntimeError("Paper account is blocked from trading.")

    if account.get("status") != "ACTIVE":
        raise RuntimeError(
            f"Paper account is not active: {account.get('status')}"
        )

    print("\nPAPER ACCOUNT VERIFIED")
    print("------------------------------")
    print("Account status:", account.get("status"))
    print("Trading blocked:", account.get("trading_blocked"))

    return account


# ============================================================
# CHECK EXISTING ORDERS
# ============================================================

def get_open_orders():

    response = requests.get(
        f"{PAPER_URL}/v2/orders",
        headers=alpaca_headers(),
        params={
            "status": "open",
            "symbols": SYMBOL,
            "limit": 100
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# CHECK CURRENT POSITION
# ============================================================

def get_position():

    response = requests.get(
        f"{PAPER_URL}/v2/positions/{SYMBOL}",
        headers=alpaca_headers(),
        timeout=30
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json()


# ============================================================
# RECORD PAPER ORDER
# ============================================================

def record_paper_order(order_data):

    ORDERS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    new_row = pd.DataFrame([order_data])

    if ORDERS_FILE.exists():

        old_orders = pd.read_csv(ORDERS_FILE)

        orders = pd.concat(
            [old_orders, new_row],
            ignore_index=True
        )

    else:
        orders = new_row

    orders.to_csv(
        ORDERS_FILE,
        index=False
    )


# ============================================================
# SUBMIT PAPER-TRADING DECISION
# ============================================================

def submit_paper_order(prediction):

    direction = prediction["direction"]

    print("\nPAPER TRADING")
    print("------------------------------")

    if not ENABLE_PAPER_TRADING:
        print("Paper trading is disabled.")
        print("Set ENABLE_PAPER_TRADING=true to enable it.")
        return

    check_paper_account()

    open_orders = get_open_orders()

    if open_orders:
        print("An MSFT order is already pending. Skipping.")
        return

    position = get_position()

    order_payload = None
    action = None

    if direction == "UP":

        if position is not None:
            print("Already holding MSFT. Skipping additional purchase.")
            return

        action = "BUY"

        order_payload = {
            "symbol": SYMBOL,
            "notional": str(BUY_AMOUNT),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "client_order_id": (
                "lr-" + prediction["bar_time_utc"].replace(":", "-")
            )
        }

    elif direction == "DOWN":

        if position is None:
            print("No MSFT position to close.")
            return

        action = "CLOSE"

        # Close the existing position, never open a short.
        response = requests.delete(
            f"{PAPER_URL}/v2/positions/{SYMBOL}",
            headers=alpaca_headers(),
            timeout=30
        )

        response.raise_for_status()

        close_result = response.json()

        record_paper_order({
            "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
            "symbol": SYMBOL,
            "action": action,
            "direction": direction,
            "order_id": close_result.get("id"),
            "status": close_result.get("status", "close_requested"),
            "predicted_change_percent": prediction[
                "predicted_change_percent"
            ]
        })

        print("Paper position close requested.")
        return

    else:
        print("FLAT prediction. No paper order.")
        return

    response = requests.post(
        f"{PAPER_URL}/v2/orders",
        headers=alpaca_headers(),
        json=order_payload,
        timeout=30
    )

    response.raise_for_status()

    order_result = response.json()

    record_paper_order({
        "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "symbol": SYMBOL,
        "action": action,
        "direction": direction,
        "order_id": order_result.get("id"),
        "status": order_result.get("status"),
        "predicted_change_percent": prediction[
            "predicted_change_percent"
        ]
    })

    print("Paper order submitted.")
    print("Action:", action)
    print("Order ID:", order_result.get("id"))
    print("Order status:", order_result.get("status"))


# ============================================================
# MAIN
# ============================================================

def main():

    print("MSFT LINEAR REGRESSION MODEL")
    print("==============================")

    print("\nTraining model...")

    model = train_model()

    print("\nRetrieving latest Alpaca market data...")

    prediction = make_prediction(model)

    is_new_prediction = save_prediction(prediction)

    if not is_new_prediction:
        print("Skipping trading because this bar was already processed.")
        return

    submit_paper_order(prediction)

    print("\nModel run completed successfully.")


if __name__ == "__main__":
    main()
