"""Cálculo de carteras: efectivo, posiciones (precio medio), ganancias realizadas y latentes en euros."""
import time

from . import db, prices


def _trades(c, account_id):
    return c.execute("SELECT * FROM trades WHERE account_id = ? ORDER BY ts, id", (account_id,)).fetchall()


def compute(account, trades, live=True):
    """Reconstruye la cartera a partir de sus operaciones (método de coste medio)."""
    cash = account["start_cash"]
    pos = {}
    realized = 0.0
    fees = 0.0
    for t in trades:
        eur = t["qty"] * t["price"] / t["fx_eur"]
        p = pos.setdefault(t["ticker"], {"ticker": t["ticker"], "name": t["name"], "qty": 0.0, "cost_eur": 0.0,
                                         "cost_local": 0.0, "currency": t["currency"]})
        fees += t["fee_eur"]
        if t["side"] == "buy":
            p["qty"] += t["qty"]
            p["cost_eur"] += eur
            p["cost_local"] += t["qty"] * t["price"]
            cash -= eur + t["fee_eur"]
        else:
            avg_eur = p["cost_eur"] / p["qty"] if p["qty"] else 0
            avg_loc = p["cost_local"] / p["qty"] if p["qty"] else 0
            realized += eur - avg_eur * t["qty"]
            p["qty"] -= t["qty"]
            p["cost_eur"] -= avg_eur * t["qty"]
            p["cost_local"] -= avg_loc * t["qty"]
            cash += eur - t["fee_eur"]
    positions = [p for p in pos.values() if p["qty"] > 1e-9]
    if live:
        prices.track([p["ticker"] for p in positions])
    invested = value = 0.0
    for p in positions:
        q = prices.get(p["ticker"], wait=live) if live else None
        p["avg_price"] = p["cost_local"] / p["qty"]
        p["quote"] = q
        if q and q.get("price_eur") is not None:
            p["value_eur"] = p["qty"] * q["price_eur"]
            p["pnl_eur"] = p["value_eur"] - p["cost_eur"]
            p["pnl_pct"] = p["pnl_eur"] / p["cost_eur"] if p["cost_eur"] else None
            # parte de la ganancia/pérdida que viene solo del precio en su moneda (sin efecto divisa)
            p["pnl_local_pct"] = q["price"] / p["avg_price"] - 1 if p["avg_price"] else None
        else:
            p["value_eur"] = p["cost_eur"]
            p["pnl_eur"] = p["pnl_pct"] = p["pnl_local_pct"] = None
        invested += p["cost_eur"]
        value += p["value_eur"]
    positions.sort(key=lambda p: -p["value_eur"])
    total = (cash if account["kind"] == "sim" else 0) + value
    base = account["start_cash"] if account["kind"] == "sim" else invested
    return {
        "id": account["id"], "name": account["name"], "kind": account["kind"],
        "start_cash": account["start_cash"], "fee_eur": account["fee_eur"],
        "cash": cash if account["kind"] == "sim" else None,
        "invested": invested, "positions_value": value, "total": total,
        "pnl_open": value - invested, "pnl_realized": realized, "fees": fees,
        "pnl_total": (total - base) if account["kind"] == "sim" else (value - invested + realized - fees),
        "pnl_total_pct": ((total - base) / base) if (account["kind"] == "sim" and base) else
                         (((value - invested + realized - fees) / invested) if invested else None),
        "positions": positions,
        "n_trades": len(trades),
    }


def accounts_for(user_id, live=True):
    with db.conn() as c:
        accs = c.execute("SELECT * FROM accounts WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
        return [compute(a, _trades(c, a["id"]), live) for a in accs]


def get_account(user_id, account_id):
    with db.conn() as c:
        a = c.execute("SELECT * FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id)).fetchone()
        if not a:
            return None, None
        return a, _trades(c, account_id)


def trade(user_id, account_id, ticker, side, qty=None, amount_eur=None, price=None, ts=None, note=None):
    """Registra una operación. En carteras ficticias el precio es siempre el de mercado."""
    a, trades = get_account(user_id, account_id)
    if not a:
        raise ValueError("Cartera no encontrada")
    q = prices.get(ticker)
    if not q:
        raise ValueError("No encuentro cotización para ese valor")
    fx = q["fx_eur"]
    if not fx:
        raise ValueError("No tengo el cambio de moneda para ese valor")
    if a["kind"] == "sim" or price is None:
        price = q["price"]
        ts = time.time()
    elif ts and ts < time.time() - 86400:
        fx = prices.fx_on(q["currency"], ts) or fx  # cambio del día de la operación
    if a["kind"] == "sim" and ts is None:
        ts = time.time()
    ts = ts or time.time()
    if qty is None:
        if not amount_eur or amount_eur <= 0:
            raise ValueError("Indica cantidad de acciones o importe en euros")
        qty = amount_eur * fx / price
    qty = round(float(qty), 6)
    if qty <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    state = compute(a, trades, live=False)
    held = next((p["qty"] for p in state["positions"] if p["ticker"] == ticker), 0)
    fee = a["fee_eur"]
    cost_eur = qty * price / fx
    if side == "buy" and a["kind"] == "sim" and cost_eur + fee > state["cash"] + 1e-6:
        raise ValueError(f"No tienes suficiente efectivo ficticio ({state['cash']:.2f} €)")
    if side == "sell" and qty > held + 1e-9:
        raise ValueError(f"Solo tienes {held:g} acciones de {ticker}")
    with db.conn() as c:
        c.execute("""INSERT INTO trades (account_id, ts, ticker, name, side, qty, price, currency, fx_eur, fee_eur, note)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (account_id, ts, ticker, q.get("name"), side, qty, price, q["currency"], fx, fee, note))
    return {"ticker": ticker, "side": side, "qty": qty, "price": price, "currency": q["currency"],
            "eur": cost_eur, "fee_eur": fee}
