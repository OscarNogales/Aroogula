def make_enriched_positions(position: dict, market_data) -> None:
    ticker = str(position.get("ticker", "")).upper().strip()
    shares = float(position.get("shares", 0) or 0)
    buy_price = float(position.get("buy_price", 0) or 0)

    try:
        current_price = market_data.get_current_price(ticker)
    except Exception:
        logger.exception("Could not enrich price for %s", ticker)
        current_price = None

    if current_price is None:
        current_price = buy_price

    current_price = float(current_price)

    cost_basis = buy_price * shares
    market_value = current_price * shares
    pnl_dollars = market_value - cost_basis
    pnl_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

    position.update({
        "current_price": round(current_price, 2),
        "cost_basis": round(cost_basis, 2),
        "market_value": round(market_value, 2),
        "pnl_dollars": round(pnl_dollars, 2),
        "pnl_pct": round(pnl_pct, 2),
    })