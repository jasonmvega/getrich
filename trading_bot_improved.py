"""A conservative, paper-first daily swing-trading bot for Alpaca.

IMPORTANT:
- This is a safer starting point, not a profitable strategy guarantee.
- It evaluates completed daily bars, so run it after the regular market close.
- Orders are disabled by default. Test and backtest before enabling them.
- Keep this file beside your existing database_manager.py and .env files.
"""

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from database_manager import create_database, save_price, save_signal

load_dotenv()
create_database()

# ---------------------------------------------------------------------------
# CONNECTION AND SAFETY SETTINGS
# ---------------------------------------------------------------------------
PAPER_URL = "https://paper-api.alpaca.markets"
BASE_URL = os.getenv("GETRICH_BASE_URL", PAPER_URL).rstrip("/")
DATA_URL = os.getenv("GETRICH_DATA_URL", "https://data.alpaca.markets").rstrip("/")
API_KEY = os.getenv("GETRICH_API_KEY") or os.getenv("API_KEY")
API_SECRET = os.getenv("GETRICH_API_SECRET") or os.getenv("API_SECRET")
DATA_FEED = os.getenv("ALPACA_DATA_FEED", "iex")

# No orders are submitted unless EXECUTE_ORDERS=true is explicitly set.
EXECUTE_ORDERS = os.getenv("EXECUTE_ORDERS", "false").strip().lower() == "true"
# A second explicit flag is required before a non-paper endpoint is accepted.
ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "false").strip().lower() == "true"

if not API_KEY or not API_SECRET:
    raise ValueError("Missing Alpaca API credentials. Set GETRICH_API_KEY and GETRICH_API_SECRET.")

if "paper-api.alpaca.markets" not in BASE_URL and not ALLOW_LIVE_TRADING:
    raise RuntimeError(
        "Safety stop: this bot is configured for a non-paper endpoint. "
        "Use the Alpaca paper endpoint while testing. Live trading requires "
        "ALLOW_LIVE_TRADING=true in addition to EXECUTE_ORDERS=true."
    )

# ---------------------------------------------------------------------------
# STRATEGY AND RISK SETTINGS
# ---------------------------------------------------------------------------
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "SPY"]

FAST_MA = 50
SLOW_MA = 200
ATR_PERIOD = 14
ATR_STOP_MULTIPLE = 2.0
ATR_TARGET_MULTIPLE = 4.0  # Target is 2x the initial stop distance.

RISK_PER_TRADE = 0.0025       # 0.25% of account equity at the planned stop distance.
MAX_POSITION_PCT = 0.05       # Maximum 5% of equity in one symbol.
MAX_TOTAL_EXPOSURE_PCT = 0.25 # Maximum 25% of equity invested by this bot.
MAX_OPEN_POSITIONS = 5
MAX_DAILY_LOSS_PCT = 0.01     # Pause NEW buys after a 1% account loss vs. prior close.

STATE_FILE = Path(__file__).with_name("trading_bot_state.json")
NEW_YORK = ZoneInfo("America/New_York")


class AlpacaAPIError(RuntimeError):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def _headers(json_body=False):
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
        "Accept": "application/json",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def api_request(base_url, path, params=None, method="GET", body=None):
    url = f"{base_url}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers=_headers(json_body=payload is not None),
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response_text = response.read().decode("utf-8")
            if not response_text:
                return {}
            return json.loads(response_text)
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise AlpacaAPIError(exc.code, f"Alpaca API {exc.code}: {error_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling Alpaca: {exc}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Timed out while calling Alpaca.") from exc


def get_market_clock():
    return api_request(BASE_URL, "/v2/clock")


def get_account():
    account = api_request(BASE_URL, "/v2/account")
    if account.get("account_blocked") or account.get("trading_blocked") or account.get("trade_suspended_by_user"):
        raise RuntimeError("Alpaca reports that this account is blocked or suspended from trading.")
    return account


def get_positions():
    rows = api_request(BASE_URL, "/v2/positions")
    positions = {}
    for row in rows:
        positions[row["symbol"]] = {
            "qty": float(row["qty"]),
            "avg_entry_price": float(row["avg_entry_price"]),
            "market_value": float(row.get("market_value", 0) or 0),
        }
    return positions


def get_open_orders():
    return api_request(
        BASE_URL,
        "/v2/orders",
        params={"status": "open", "limit": 500, "nested": "true"},
    )


def get_historical_bars(symbol):
    """Fetch split-adjusted daily OHLC bars, following every page token."""
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=450)
    params = {
        "timeframe": "1Day",
        "feed": DATA_FEED,
        "adjustment": "split",
        "sort": "asc",
        "limit": 1000,
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
    }

    bars = []
    while True:
        response = api_request(DATA_URL, f"/v2/stocks/{symbol}/bars", params=params)
        bars.extend(response.get("bars", []))
        next_token = response.get("next_page_token")
        if not next_token:
            break
        params["page_token"] = next_token

    bars.sort(key=lambda item: item["t"])
    return bars


def sma(values, period):
    if len(values) < period:
        raise ValueError(f"Need {period} values for SMA, received {len(values)}.")
    return sum(values[-period:]) / period


def average_true_range(bars, period=ATR_PERIOD):
    if len(bars) < period + 1:
        raise ValueError(f"Need at least {period + 1} bars for ATR.")

    true_ranges = []
    for index in range(1, len(bars)):
        high = float(bars[index]["h"])
        low = float(bars[index]["l"])
        previous_close = float(bars[index - 1]["c"])
        true_ranges.append(max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        ))

    return sum(true_ranges[-period:]) / period


def bar_date_et(bar):
    timestamp = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
    return timestamp.astimezone(NEW_YORK).date().isoformat()


def format_price(price):
    decimals = 2 if price >= 1 else 4
    return f"{price:.{decimals}f}"


def format_quantity(quantity):
    return f"{quantity:.6f}".rstrip("0").rstrip(".")


def load_state():
    if not STATE_FILE.exists():
        return {"last_processed": {}}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        state.setdefault("last_processed", {})
        return state
    except (OSError, json.JSONDecodeError):
        print("WARNING: Could not read bot state file; starting with empty run state.")
        return {"last_processed": {}}


def save_state(state):
    temporary_file = STATE_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    temporary_file.replace(STATE_FILE)


def get_symbol_open_orders(open_orders, symbol):
    return [order for order in open_orders if order.get("symbol") == symbol]


def estimate_pending_buy_exposure(open_orders, latest_prices):
    reserved = 0.0
    pending_symbols = set()
    for order in open_orders:
        if order.get("side") != "buy":
            continue
        symbol = order.get("symbol")
        if not symbol:
            continue
        pending_symbols.add(symbol)
        if order.get("notional"):
            reserved += float(order["notional"])
        else:
            qty = float(order.get("qty") or 0)
            reference_price = float(order.get("limit_price") or latest_prices.get(symbol, 0))
            reserved += qty * reference_price
    return reserved, pending_symbols


def save_bot_signal(symbol, timestamp, decision, reason):
    save_signal(
        ticker=symbol,
        recorded_at=timestamp,
        decision=decision,
        reason=reason,
    )


def submit_bracket_buy(symbol, quantity, entry_limit, stop_price, target_price):
    order = {
        "symbol": symbol,
        "qty": str(int(quantity)),
        "side": "buy",
        "type": "limit",
        "limit_price": format_price(entry_limit),
        "time_in_force": "day",
        "order_class": "bracket",
        "take_profit": {"limit_price": format_price(target_price)},
        "stop_loss": {"stop_price": format_price(stop_price)},
        "client_order_id": f"swingbot-{symbol}-{datetime.now(NEW_YORK):%Y%m%d}",
    }
    return api_request(BASE_URL, "/v2/orders", method="POST", body=order)


def submit_market_sell(symbol, quantity):
    order = {
        "symbol": symbol,
        "qty": format_quantity(quantity),
        "side": "sell",
        "type": "market",
        "time_in_force": "day",
        "client_order_id": f"swingbot-exit-{symbol}-{datetime.now(NEW_YORK):%Y%m%d}",
    }
    return api_request(BASE_URL, "/v2/orders", method="POST", body=order)


def evaluate_symbol(symbol, bars, account_equity, buying_power, exposure,
                    open_position_count, position, open_orders_for_symbol,
                    block_new_buys):
    if len(bars) < SLOW_MA + 1:
        print(f"{symbol}: SKIP — only {len(bars)} daily bars; need at least {SLOW_MA + 1}.")
        return exposure, open_position_count, False

    closes = [float(bar["c"]) for bar in bars]
    close = closes[-1]
    atr = average_true_range(bars)
    current_fast = sma(closes, FAST_MA)
    current_slow = sma(closes, SLOW_MA)
    previous_fast = sma(closes[:-1], FAST_MA)
    previous_slow = sma(closes[:-1], SLOW_MA)

    golden_cross = previous_fast <= previous_slow and current_fast > current_slow and close > current_slow
    death_cross = previous_fast >= previous_slow and current_fast < current_slow

    print(
        f"{symbol}: close=${close:.2f} | SMA{FAST_MA}=${current_fast:.2f} "
        f"| SMA{SLOW_MA}=${current_slow:.2f} | ATR{ATR_PERIOD}=${atr:.2f}"
    )

    if position and position["qty"] < 0:
        print(f"{symbol}: SKIP — an existing short position is present; this bot only manages long positions.")
        save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "REVIEW", "Existing short position detected")
        return exposure, open_position_count, False

    if position and position["qty"] > 0:
        entry = position["avg_entry_price"]
        qty = position["qty"]
        # Legacy positions without a broker-side stop get a conservative daily-close exit rule.
        stop_level = max(entry * 0.92, entry - ATR_STOP_MULTIPLE * atr)
        stop_triggered = close <= stop_level

        if stop_triggered or death_cross:
            reason = (
                f"Daily close ${close:.2f} reached legacy risk exit ${stop_level:.2f}"
                if stop_triggered else "50-day SMA crossed below 200-day SMA"
            )
            if open_orders_for_symbol:
                print(f"{symbol}: EXIT SIGNAL, but open order(s) exist. No order sent; review these orders first.")
                save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "REVIEW", reason)
                return exposure, open_position_count, False

            print(f"{symbol}: SELL {qty:g} shares — {reason}")
            save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "SELL", reason)
            if EXECUTE_ORDERS:
                result = submit_market_sell(symbol, qty)
                print(f"{symbol}: sell order submitted: {result.get('id', 'unknown order id')}")
            else:
                print(f"{symbol}: DRY RUN — no order submitted.")
            return exposure, max(0, open_position_count - 1), False

        print(f"{symbol}: HOLD — existing position; no exit condition.")
        save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "HOLD", "Existing position; risk exit not triggered")
        return exposure, open_position_count, False

    if open_orders_for_symbol:
        print(f"{symbol}: SKIP — an order is already open for this ticker.")
        return exposure, open_position_count, False

    if not golden_cross:
        print(f"{symbol}: HOLD — no new golden-cross entry.")
        save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "HOLD", "No new 50/200-day bullish crossover")
        return exposure, open_position_count, False

    if block_new_buys:
        print(f"{symbol}: BUY BLOCKED — account daily loss limit reached.")
        save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "BLOCKED", "Daily loss guard blocked new entries")
        return exposure, open_position_count, False

    if open_position_count >= MAX_OPEN_POSITIONS:
        print(f"{symbol}: BUY BLOCKED — maximum number of positions already reached.")
        save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "BLOCKED", "Maximum open positions reached")
        return exposure, open_position_count, False

    stop_distance = ATR_STOP_MULTIPLE * atr
    if atr <= 0 or stop_distance <= 0 or close <= stop_distance:
        print(f"{symbol}: BUY BLOCKED — invalid ATR/stop calculation.")
        return exposure, open_position_count, False

    risk_budget = account_equity * RISK_PER_TRADE
    max_position_dollars = account_equity * MAX_POSITION_PCT
    max_total_dollars = account_equity * MAX_TOTAL_EXPOSURE_PCT
    remaining_exposure = max(0.0, max_total_dollars - exposure)
    # buying_power already reflects broker-side holds; equity minus gross exposure
    # adds a separate no-leverage ceiling without subtracting holdings twice.
    available_cash_budget = max(0.0, min(buying_power, account_equity - exposure))

    shares_by_risk = math.floor(risk_budget / stop_distance)
    shares_by_position_cap = math.floor(max_position_dollars / close)
    shares_by_total_cap = math.floor(remaining_exposure / close)
    shares_by_buying_power = math.floor(available_cash_budget / close)
    quantity = min(shares_by_risk, shares_by_position_cap, shares_by_total_cap, shares_by_buying_power)

    if quantity < 1:
        print(f"{symbol}: BUY BLOCKED — risk/position/exposure budget allows fewer than 1 share.")
        save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "BLOCKED", "Position sizing returned fewer than one share")
        return exposure, open_position_count, False

    stop_price = close - stop_distance
    target_price = close + ATR_TARGET_MULTIPLE * atr
    entry_limit = close * 1.003  # Do not chase an opening gap more than 0.3% above the signal close.
    estimated_notional = quantity * entry_limit
    reason = (
        f"50/200-day golden cross; {quantity} shares; limit entry ${entry_limit:.2f}; "
        f"planned stop ${stop_price:.2f}; "
        f"target ${target_price:.2f}; estimated notional ${estimated_notional:.2f}"
    )

    print(f"{symbol}: BUY PLAN — {reason}")
    save_bot_signal(symbol, datetime.now(timezone.utc).isoformat(), "BUY", reason)

    if EXECUTE_ORDERS:
        result = submit_bracket_buy(symbol, quantity, entry_limit, stop_price, target_price)
        print(f"{symbol}: bracket order submitted: {result.get('id', 'unknown order id')}")
    else:
        print(f"{symbol}: DRY RUN — no order submitted.")

    return exposure + estimated_notional, open_position_count + 1, True


def main():
    print("=" * 68)
    print("CONSERVATIVE DAILY SWING BOT")
    print(f"Trading endpoint: {BASE_URL}")
    print(f"Order execution enabled: {EXECUTE_ORDERS}")
    print("=" * 68)

    clock = get_market_clock()
    if clock.get("is_open"):
        print("Market is currently open. Skipping so incomplete daily bars are not used.")
        return

    account = get_account()
    equity = float(account.get("equity", 0) or 0)
    buying_power = float(account.get("buying_power", 0) or 0)
    previous_equity = float(account.get("last_equity", 0) or 0)
    if equity <= 0:
        raise RuntimeError(f"Invalid account equity returned by Alpaca: {equity}")

    daily_change = (equity - previous_equity) / previous_equity if previous_equity > 0 else 0.0
    block_new_buys = daily_change <= -MAX_DAILY_LOSS_PCT
    print(f"Account equity: ${equity:,.2f} | Buying power: ${buying_power:,.2f} | Daily change: {daily_change:.2%}")
    if block_new_buys:
        print("Daily loss guard is active: new buys are disabled for this run; existing positions can still exit.")

    positions = get_positions()
    open_orders = get_open_orders()

    latest_prices = {}
    market_data = {}
    for symbol in SYMBOLS:
        try:
            bars = get_historical_bars(symbol)
            if not bars:
                print(f"{symbol}: no historical bars returned.")
                continue
            market_data[symbol] = bars
            latest_prices[symbol] = float(bars[-1]["c"])
            for bar in bars:
                save_price(ticker=symbol, recorded_at=str(bar["t"]), price=float(bar["c"]))
        except Exception as exc:
            print(f"{symbol}: data error — {exc}")

    pending_buy_exposure, pending_buy_symbols = estimate_pending_buy_exposure(open_orders, latest_prices)
    current_exposure = sum(abs(position["market_value"]) for position in positions.values())
    exposure = current_exposure + pending_buy_exposure
    open_position_symbols = set(positions) | pending_buy_symbols
    open_position_count = len(open_position_symbols)

    print(f"Current long exposure: ${current_exposure:,.2f}")
    print(f"Estimated pending buy exposure: ${pending_buy_exposure:,.2f}")
    print(f"Total counted exposure: ${exposure:,.2f} / ${equity * MAX_TOTAL_EXPOSURE_PCT:,.2f} cap")

    state = load_state()
    changed_state = False

    for symbol in SYMBOLS:
        bars = market_data.get(symbol)
        if not bars:
            continue

        latest_bar_date = bar_date_et(bars[-1])
        if EXECUTE_ORDERS and state["last_processed"].get(symbol) == latest_bar_date:
            print(f"{symbol}: already processed completed bar for {latest_bar_date}; skipping duplicate run.")
            continue

        symbol_orders = get_symbol_open_orders(open_orders, symbol)
        try:
            exposure, open_position_count, _ = evaluate_symbol(
                symbol=symbol,
                bars=bars,
                account_equity=equity,
                buying_power=buying_power,
                exposure=exposure,
                open_position_count=open_position_count,
                position=positions.get(symbol),
                open_orders_for_symbol=symbol_orders,
                block_new_buys=block_new_buys,
            )
            if EXECUTE_ORDERS:
                state["last_processed"][symbol] = latest_bar_date
                changed_state = True
        except Exception as exc:
            print(f"{symbol}: trading logic error — {exc}")

    if changed_state:
        save_state(state)

    print("=" * 68)
    print("Run complete. Review Alpaca order status and the database signals before the next run.")
    print("=" * 68)


if __name__ == "__main__":
    main()
