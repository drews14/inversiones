"""Precios al momento: caché en memoria que se refresca en segundo plano.

- EE. UU. y divisas: tiempo real en Yahoo.
- Europa: ~15 min de retraso (licencias de las bolsas). Japón: ~20 min.
El retraso real se mide comparando la hora del último dato con la hora actual.
"""
import threading
import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

REFRESH_SECONDS = 30
_lock = threading.Lock()
_cache = {}        # ticker -> {price, prev_close, currency, name, ts, delay_min}
_meta = {}         # ticker -> {currency, name, prev_close, day}
_tracked = {}      # ticker -> último momento en que alguien lo pidió
_fx = {"EUR": 1.0}  # moneda -> unidades por 1 EUR


def fx_pair(cur):
    return None if cur in ("EUR", None, "") else f"EUR{'GBP' if cur == 'GBp' else cur}=X"


def eur_rate(cur):
    """Unidades de la moneda por 1 EUR (para GBp, peniques por EUR)."""
    if cur in ("EUR", None, ""):
        return 1.0
    base = _fx.get("GBP" if cur == "GBp" else cur)
    if base is None:
        return None
    return base * 100 if cur == "GBp" else base


def _load_meta(ticker):
    today = datetime.now(timezone.utc).date()
    m = _meta.get(ticker)
    if m and m["day"] == today:
        return m
    t = yf.Ticker(ticker)
    fi = t.fast_info
    name = None
    try:
        info = t.info or {}
        name = info.get("shortName") or info.get("longName")
    except Exception:
        pass
    m = {"currency": fi.get("currency") or "USD", "prev_close": fi.get("previousClose"),
         "name": name or ticker, "day": today}
    _meta[ticker] = m
    return m


def _refresh(tickers):
    if not tickers:
        return
    metas = {}
    for t in tickers:
        try:
            metas[t] = _load_meta(t)
        except Exception:
            pass
    curs = {m["currency"] for m in metas.values()}
    pairs = sorted({p for p in (fx_pair(c) for c in curs) if p})
    syms = sorted(set(metas) | set(pairs))
    df = yf.download(syms, period="5d", interval="1m", progress=False, auto_adjust=False, threads=True)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(syms[0])
    now = datetime.now(timezone.utc)
    with _lock:
        for p in pairs:
            if p in df and df[p].dropna().size:
                _fx[p[3:6]] = float(df[p].dropna().iloc[-1])
        for t, m in metas.items():
            if t not in df:
                continue
            s = df[t].dropna()
            if not s.size:
                continue
            last_ts = s.index[-1].to_pydatetime()
            _cache[t] = {"ticker": t, "name": m["name"], "currency": m["currency"],
                         "price": float(s.iloc[-1]), "prev_close": m["prev_close"],
                         "ts": last_ts.isoformat(), "age_min": int((now - last_ts).total_seconds() // 60),
                         "updated": time.time()}


def fx_on(cur, ts):
    """Cambio (unidades por 1 EUR) en una fecha pasada, para operaciones reales antiguas."""
    pair = fx_pair(cur)
    if not pair:
        return 1.0
    day = datetime.fromtimestamp(ts, timezone.utc).date()
    df = yf.download(pair, start=str(day - pd.Timedelta(days=7)), end=str(day + pd.Timedelta(days=1)),
                     progress=False, auto_adjust=False)["Close"]
    s = df.squeeze().dropna() if hasattr(df, "squeeze") else df.dropna()
    if not len(s):
        return None
    rate = float(s.iloc[-1])
    return rate * 100 if cur == "GBp" else rate


def track(tickers):
    now = time.time()
    with _lock:
        for t in tickers:
            _tracked[t.upper()] = now


def get(ticker, wait=True):
    """Devuelve la cotización (la descarga al momento si aún no está en caché)."""
    ticker = ticker.upper()
    track([ticker])
    with _lock:
        q = _cache.get(ticker)
    if q or not wait:
        return _with_eur(q)
    _refresh([ticker])
    with _lock:
        return _with_eur(_cache.get(ticker))


def _with_eur(q):
    if not q:
        return None
    q = dict(q)
    rate = eur_rate(q["currency"])
    q["fx_eur"] = rate
    q["price_eur"] = q["price"] / rate if rate else None
    q["chg_day"] = (q["price"] / q["prev_close"] - 1) if q.get("prev_close") else None
    # retraso típico según mercado (Yahoo gratis)
    q["realtime"] = not any(q["ticker"].endswith(s) for s in (".MC", ".DE", ".PA", ".AS", ".MI", ".L", ".T", ".SW", ".BR", ".LS"))
    return q


def snapshot(tickers):
    with _lock:
        return {t: _with_eur(_cache.get(t)) for t in tickers if _cache.get(t)}


def search(query):
    res = []
    for q in yf.Search(query, max_results=10).quotes:
        if q.get("quoteType") in ("EQUITY", "ETF") and q.get("symbol"):
            res.append({"ticker": q["symbol"], "name": " ".join((q.get("shortname") or q.get("longname") or "").split()),
                        "exchange": q.get("exchDisp") or q.get("exchange"), "type": q.get("quoteType")})
    return res


def _loop():
    while True:
        try:
            cutoff = time.time() - 3600  # deja de seguir lo que nadie mira en 1 h (salvo carteras, que se re-registran)
            with _lock:
                tickers = [t for t, ts in _tracked.items() if ts > cutoff]
            for i in range(0, len(tickers), 100):
                _refresh(tickers[i:i + 100])
        except Exception as e:
            print("Error refrescando precios:", e)
        time.sleep(REFRESH_SECONDS)


def start():
    threading.Thread(target=_loop, daemon=True, name="precios").start()
