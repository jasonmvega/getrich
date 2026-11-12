"""Hybrid intraday/swing Alpaca bot. Paper-first; dry-run unless explicitly enabled.

Strategy:
- Higher-timeframe filter: completed daily EMA20 > EMA50 and daily close > EMA20.
- Intraday trigger: completed 5-minute EMA9 crosses above EMA21, with RSI(14) 50-70.
- Existing positions: broker-side bracket orders protect entries; legacy positions without
  open orders may exit on a bearish 5-minute EMA cross or ATR-based close stop.
- Five GitHub Actions evaluations per trading day are scheduled in the workflow YAML.

This is an experimental rules-based strategy, not a promise of profitability. Keep it in
Alpaca paper trading and evaluate it over a meaningful sample before considering live use.
"""

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from database_manager import create_database, save_price, save_signal
    create_database()
    DB_ENABLED = True
except (ImportError, Exception) as exc:
    DB_ENABLED = False
    print(f"Database logging disabled: {exc}")

# ---------------------------- Connection -----------------------------------
PAPER_URL = "https://paper-api.alpaca.markets"
BASE_URL = os.getenv("GETRICH_BASE_URL", PAPER_URL).rstrip("/")
DATA_URL = os.getenv("GETRICH_DATA_URL", "https://data.alpaca.markets").rstrip("/")
API_KEY = os.getenv("GETRICH_API_KEY") or os.getenv("API_KEY")
API_SECRET = os.getenv("GETRICH_API_SECRET") or os.getenv("API_SECRET")
DATA_FEED = os.getenv("ALPACA_DATA_FEED", "iex")
EXECUTE_ORDERS = os.getenv("EXECUTE_ORDERS", "false").strip().lower() == "true"
ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "false").strip().lower() == "true"

if not API_KEY or not API_SECRET:
    raise RuntimeError("Missing GETRICH_API_KEY / GETRICH_API_SECRET GitHub secrets.")
if BASE_URL != PAPER_URL and not ALLOW_LIVE_TRADING:
    raise RuntimeError("Safety stop: use https://paper-api.alpaca.markets. Live endpoint rejected.")
if BASE_URL != PAPER_URL:
    raise RuntimeError("This build is paper-only. Live trading is intentionally unsupported.")

# ------------------------------ Strategy -----------------------------------
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "SPY"]
INTRADAY_TIMEFRAME = "5Min"
DAILY_FAST_EMA = 20
DAILY_SLOW_EMA = 50
INTRADAY_FAST_EMA = 9
INTRADAY_SLOW_EMA = 21
RSI_PERIOD = 14
ATR_PERIOD = 14
STOP_ATR_MULTIPLE = 2.0
TARGET_R_MULTIPLE = 2.0
RISK_PER_TRADE = 0.0025          # 0.25% of equity at planned stop distance
MAX_POSITION_PCT = 0.05         # 5% of equity per ticker
MAX_TOTAL_EXPOSURE_PCT = 0.25   # 25% gross exposure cap for this bot
MAX_OPEN_POSITIONS = 5
MAX_DAILY_LOSS_PCT = 0.01       # block new entries after 1% daily equity loss
MAX_ENTRY_CHASE_PCT = 0.002     # limit entry no more than 0.2% above last completed 5m close
NY = ZoneInfo("America/New_York")


def headers(json_body=False):
    h = {"APCA-API-KEY-ID": API_KEY, "APCA-API-SECRET-KEY": API_SECRET, "Accept": "application/json"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def request(base, path, params=None, method="GET", body=None):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers(payload is not None), method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Alpaca HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Alpaca network error: {exc}") from exc


def api(path, params=None, method="GET", body=None):
    return request(BASE_URL, path, params, method, body)


def data_api(path, params=None):
    return request(DATA_URL, path, params)


def get_bars(symbol, timeframe, lookback_days, limit=1000):
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=lookback_days)
    params = {
        "timeframe": timeframe,
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
        "adjustment": "split",
        "feed": DATA_FEED,
        "sort": "asc",
        "limit": limit,
    }
    result = []
    while True:
        payload = data_api(f"/v2/stocks/{symbol}/bars", params)
        result.extend(payload.get("bars", []))
        token = payload.get("next_page_token")
        if not token:
            break
        params["page_token"] = token
    result.sort(key=lambda b: b["t"])
    return result


def bar_datetime(bar):
    return datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))


def completed_bars(bars, minutes):
    """Discard the newest bar unless its full interval has elapsed."""
    now = datetime.now(timezone.utc)
    return [b for b in bars if bar_datetime(b) + timedelta(minutes=minutes) <= now]


def ema(values, period):
    if len(values) < period:
        raise ValueError(f"EMA{period} needs at least {period} values; got {len(values)}")
    alpha = 2.0 / (period + 1.0)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = alpha * item + (1.0 - alpha) * value
    return value


def ema_series(values, period):
    if len(values) < period + 1:
        raise ValueError(f"EMA{period} series needs at least {period + 1} values")
    alpha = 2.0 / (period + 1.0)
    current = sum(values[:period]) / period
    output = [None] * (period - 1) + [current]
    for item in values[period:]:
        current = alpha * item + (1.0 - alpha) * current
        output.append(current)
    return output


def rsi(values, period=RSI_PERIOD):
    if len(values) < period + 1:
        raise ValueError("Not enough closes for RSI")
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(x, 0.0) for x in changes]
    losses = [max(-x, 0.0) for x in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(changes)):
        avg_gain = ((period - 1) * avg_gain + gains[i]) / period
        avg_loss = ((period - 1) * avg_loss + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(bars, period=ATR_PERIOD):
    if len(bars) < period + 1:
        raise ValueError("Not enough bars for ATR")
    ranges = []
    for i in range(1, len(bars)):
        high, low = float(bars[i]["h"]), float(bars[i]["l"])
        prev_close = float(bars[i - 1]["c"])
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(ranges[-period:]) / period


def record(symbol, timestamp, decision, reason):
    if DB_ENABLED:
        try:
            save_signal(ticker=symbol, recorded_at=timestamp, decision=decision, reason=reason)
        except Exception as exc:
            print(f"WARNING: could not save signal for {symbol}: {exc}")


def record_prices(symbol, bars):
    if DB_ENABLED:
        for b in bars:
            try:
                save_price(ticker=symbol, recorded_at=b["t"], price=float(b["c"]))
            except Exception as exc:
                print(f"WARNING: could not save price for {symbol}: {exc}")
                break


def money(x):
    return f"{x:.2f}" if x >= 1 else f"{x:.4f}"


def qty_text(q):
    return f"{q:.6f}".rstrip("0").rstrip(".")


def get_account():
    account = api("/v2/account")
    if account.get("account_blocked") or account.get("trading_blocked") or account.get("trade_suspended_by_user"):
        raise RuntimeError("Alpaca account is blocked or trading-suspended")
    return account


def get_positions():
    rows = api("/v2/positions")
    return {r["symbol"]: {"qty": float(r["qty"]), "avg": float(r["avg_entry_price"]),
                          "market_value": abs(float(r.get("market_value", 0) or 0))} for r in rows}


def get_open_orders():
    return api("/v2/orders", {"status": "open", "limit": 500, "nested": "true"})


def symbol_orders(orders, symbol):
    return [o for o in orders if o.get("symbol") == symbol]


def pending_buy_exposure(orders, prices):
    total, symbols = 0.0, set()
    for order in orders:
        if order.get("side") != "buy":
            continue
        sym = order.get("symbol")
        if not sym:
            continue
        symbols.add(sym)
        qty = float(order.get("qty") or 0)
        px = float(order.get("limit_price") or prices.get(sym, 0))
        total += float(order.get("notional") or qty * px)
    return total, symbols


def submit_bracket(symbol, quantity, entry, stop, target, signal_bar_time):
    stamp = bar_datetime({"t": signal_bar_time}).astimezone(NY).strftime("%Y%m%d%H%M")
    client_id = f"hybrid-{symbol}-{stamp}"[:48]
    body = {
        "symbol": symbol,
        "qty": str(int(quantity)),
        "side": "buy",
        "type": "limit",
        "limit_price": money(entry),
        "time_in_force": "gtc",
        "order_class": "bracket",
        "take_profit": {"limit_price": money(target)},
        "stop_loss": {"stop_price": money(stop)},
        "client_order_id": client_id,
    }
    return api("/v2/orders", method="POST", body=body)


def submit_market_sell(symbol, quantity, signal_bar_time):
    stamp = bar_datetime({"t": signal_bar_time}).astimezone(NY).strftime("%Y%m%d%H%M")
    body = {
        "symbol": symbol,
        "qty": qty_text(quantity),
        "side": "sell",
        "type": "market",
        "time_in_force": "day",
        "client_order_id": f"hybrid-exit-{symbol}-{stamp}"[:48],
    }
    return api("/v2/orders", method="POST", body=body)


def evaluate(symbol, daily, intraday, account_equity, buying_power, gross_exposure,
             open_symbols, position, orders_for_symbol, block_buys):
    dclose = [float(b["c"]) for b in daily]
    iclose = [float(b["c"]) for b in intraday]
    if len(dclose) < DAILY_SLOW_EMA or len(iclose) < max(INTRADAY_SLOW_EMA + 2, RSI_PERIOD + 2, ATR_PERIOD + 2):
        print(f"{symbol}: SKIP — insufficient completed bars (daily={len(dclose)}, 5m={len(iclose)})")
        return gross_exposure, open_symbols

    dfast, dslow = ema(dclose, DAILY_FAST_EMA), ema(dclose, DAILY_SLOW_EMA)
    daily_bullish = dfast > dslow and dclose[-1] > dfast
    fast = ema_series(iclose, INTRADAY_FAST_EMA)
    slow = ema_series(iclose, INTRADAY_SLOW_EMA)
    bullish_cross = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
    bearish_cross = fast[-2] >= slow[-2] and fast[-1] < slow[-1]
    last_close = iclose[-1]
    current_rsi = rsi(iclose)
    current_atr = atr(intraday)
    signal_time = intraday[-1]["t"]
    signal_iso = bar_datetime(intraday[-1]).isoformat()

    print(f"{symbol}: 5m=${last_close:.2f} | Daily EMA20/50={dfast:.2f}/{dslow:.2f} "
          f"| 5m EMA9/21={fast[-1]:.2f}/{slow[-1]:.2f} | RSI={current_rsi:.1f} | ATR={current_atr:.3f}")

    if position and position["qty"] < 0:
        print(f"{symbol}: REVIEW — short position detected; this bot does not manage shorts")
        record(symbol, signal_iso, "REVIEW", "Short position detected; bot is long-only")
        return gross_exposure, open_symbols

    if position and position["qty"] > 0:
        if orders_for_symbol:
            print(f"{symbol}: HOLD — open broker order(s) detected; protective bracket may be active")
            record(symbol, signal_iso, "HOLD", "Open order exists; no duplicate exit submitted")
            return gross_exposure, open_symbols
        stop_level = position["avg"] - STOP_ATR_MULTIPLE * current_atr
        if bearish_cross or last_close <= stop_level:
            reason = "Bearish 5-minute EMA cross" if bearish_cross else f"5-minute close reached ATR risk level ${stop_level:.2f}"
            print(f"{symbol}: EXIT PLAN — {reason}; sell {position['qty']:g}")
            record(symbol, signal_iso, "SELL", reason)
            if EXECUTE_ORDERS:
                result = submit_market_sell(symbol, abs(position["qty"]), signal_time)
                print(f"{symbol}: sell submitted, order id={result.get('id', 'unknown')}")
            else:
                print(f"{symbol}: DRY RUN — no order submitted")
        else:
            print(f"{symbol}: HOLD — no exit condition")
            record(symbol, signal_iso, "HOLD", "Position held; no exit condition")
        return gross_exposure, open_symbols

    if orders_for_symbol:
        print(f"{symbol}: SKIP — an open order already exists")
        return gross_exposure, open_symbols

    # Entry requires both higher-timeframe trend and fresh intraday momentum.
    if not daily_bullish or not bullish_cross or not (50.0 <= current_rsi <= 70.0):
        reason = "No aligned daily-uptrend + 5m bullish cross + RSI 50-70 setup"
        print(f"{symbol}: HOLD — {reason}")
        record(symbol, signal_iso, "HOLD", reason)
        return gross_exposure, open_symbols

    if block_buys:
        print(f"{symbol}: BLOCKED — daily account loss guard is active")
        record(symbol, signal_iso, "BLOCKED", "Daily loss guard blocked new entry")
        return gross_exposure, open_symbols
    if len(open_symbols) >= MAX_OPEN_POSITIONS:
        print(f"{symbol}: BLOCKED — max open positions reached")
        record(symbol, signal_iso, "BLOCKED", "Maximum open positions reached")
        return gross_exposure, open_symbols

    stop_distance = STOP_ATR_MULTIPLE * current_atr
    if current_atr <= 0 or stop_distance <= 0 or last_close <= stop_distance:
        print(f"{symbol}: BLOCKED — invalid ATR/stop distance")
        return gross_exposure, open_symbols

    risk_dollars = account_equity * RISK_PER_TRADE
    max_position_dollars = account_equity * MAX_POSITION_PCT
    max_total_dollars = account_equity * MAX_TOTAL_EXPOSURE_PCT
    remaining_exposure = max(0.0, max_total_dollars - gross_exposure)
    cash_budget = max(0.0, min(buying_power, account_equity - gross_exposure))
    qty = min(
        math.floor(risk_dollars / stop_distance),
        math.floor(max_position_dollars / last_close),
        math.floor(remaining_exposure / last_close),
        math.floor(cash_budget / last_close),
    )
    if qty < 1:
        print(f"{symbol}: BLOCKED — risk and exposure limits allow less than one share")
        record(symbol, signal_iso, "BLOCKED", "Position sizing allowed fewer than one share")
        return gross_exposure, open_symbols

    entry = last_close * (1.0 + MAX_ENTRY_CHASE_PCT)
    stop = last_close - stop_distance
    target = last_close + TARGET_R_MULTIPLE * stop_distance
    notional = qty * entry
    reason = (f"Hybrid entry: daily EMA20>EMA50; 5m EMA9 crossed above EMA21; RSI={current_rsi:.1f}; "
              f"qty={qty}; limit=${entry:.2f}; planned stop=${stop:.2f}; target=${target:.2f}; "
              f"estimated notional=${notional:.2f}")
    print(f"{symbol}: BUY PLAN — {reason}")
    record(symbol, signal_iso, "BUY", reason)
    if EXECUTE_ORDERS:
        result = submit_bracket(symbol, qty, entry, stop, target, signal_time)
        print(f"{symbol}: bracket submitted, order id={result.get('id', 'unknown')}")
    else:
        print(f"{symbol}: DRY RUN — no order submitted")
    open_symbols = set(open_symbols)
    open_symbols.add(symbol)
    return gross_exposure + notional, open_symbols


def main():
    print("=" * 72)
    print("HYBRID INTRADAY + SWING BOT | ALPACA PAPER ONLY")
    print(f"Trading endpoint: {BASE_URL}")
    print(f"Order execution enabled: {EXECUTE_ORDERS}")
    print(f"Database logging enabled: {DB_ENABLED}")
    print("Evaluations are scheduled by GitHub Actions; no trade is forced per run.")
    print("=" * 72)

    clock = api("/v2/clock")
    if not clock.get("is_open"):
        print("Market is closed. No evaluation or order submission.")
        return

    account = get_account()
    equity = float(account.get("equity", 0) or 0)
    buying_power = float(account.get("buying_power", 0) or 0)
    previous_equity = float(account.get("last_equity", 0) or 0)
    if equity <= 0:
        raise RuntimeError(f"Invalid account equity: {equity}")
    daily_change = (equity - previous_equity) / previous_equity if previous_equity > 0 else 0.0
    block_buys = daily_change <= -MAX_DAILY_LOSS_PCT
    print(f"Equity=${equity:,.2f} | buying power=${buying_power:,.2f} | daily change={daily_change:.2%}")
    if block_buys:
        print("Daily loss guard active: new entries blocked; exit management remains active")

    positions = get_positions()
    orders = get_open_orders()
    daily_data, intraday_data, latest_prices = {}, {}, {}
    for symbol in SYMBOLS:
        try:
            daily = completed_bars(get_bars(symbol, "1Day", 160), 24 * 60)
            intra = completed_bars(get_bars(symbol, INTRADAY_TIMEFRAME, 7), 5)
            # Filter daily data to completed sessions before the current New York date.
            today_ny = datetime.now(NY).date()
            daily = [b for b in daily if bar_datetime(b).astimezone(NY).date() < today_ny]
            if daily and intra:
                daily_data[symbol] = daily
                intraday_data[symbol] = intra
                latest_prices[symbol] = float(intra[-1]["c"])
                record_prices(symbol, intra[-20:])
            else:
                print(f"{symbol}: no usable completed daily/intraday bars")
        except Exception as exc:
            print(f"{symbol}: market-data error — {exc}")

    pending, pending_symbols = pending_buy_exposure(orders, latest_prices)
    positions_value = sum(p["market_value"] for p in positions.values())
    gross_exposure = positions_value + pending
    open_symbols = set(positions) | pending_symbols
    print(f"Gross exposure=${gross_exposure:,.2f} / cap=${equity * MAX_TOTAL_EXPOSURE_PCT:,.2f}")

    for symbol in SYMBOLS:
        daily, intra = daily_data.get(symbol), intraday_data.get(symbol)
        if not daily or not intra:
            continue
        try:
            gross_exposure, open_symbols = evaluate(
                symbol, daily, intra, equity, buying_power, gross_exposure,
                open_symbols, positions.get(symbol), symbol_orders(orders, symbol), block_buys
            )
        except Exception as exc:
            print(f"{symbol}: evaluation error — {exc}")

    print("=" * 72)
    print("Evaluation complete. Check Alpaca paper orders and logs before the next run.")
    print("=" * 72)


if __name__ == "__main__":
    main()
