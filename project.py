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
