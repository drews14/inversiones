"""Precios al momento: caché en memoria que se refresca en segundo plano.

- EE. UU. y divisas: tiempo real en Yahoo.
- Europa: ~15 min de retraso (licencias de las bolsas). Japón: ~20 min.
El retraso real se mide comparando la hora del último dato con la hora actual.
"""
import re
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


_last_ok = {"t": 0.0}  # último refresco correcto (se ve en /api/health)


def _download_close(syms, period):
    df = yf.download(syms, period=period, interval="1m", progress=False, auto_adjust=False,
                     threads=True, timeout=20)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(syms[0])
    return df


def _last(df, sym):
    if sym not in df:
        return None
    s = df[sym].dropna()
    return (s.index[-1].to_pydatetime(), float(s.iloc[-1])) if s.size else None


def _refresh(tickers):
    """Descarga el último precio de cada valor. Si Yahoo falla para alguno, NO se queda el precio viejo como
    si fuera actual: se guarda cuándo se consiguió de verdad («updated») y la app avisa si es antiguo."""
    if not tickers:
        return
    metas = {}
    for t in tickers:
        try:
            metas[t] = _load_meta(t)
        except Exception as e:
            print(f"Sin datos básicos de {t}: {e}", flush=True)
    curs = {m["currency"] for m in metas.values()}
    pairs = sorted({p for p in (fx_pair(c) for c in curs) if p})
    syms = sorted(set(metas) | set(pairs))
    if not syms:
        return
    got = {}
    try:
        df = _download_close(syms, "1d")           # hoy: rápido y ligero
        for s in syms:
            v = _last(df, s)
            if v:
                got[s] = v
    except Exception as e:
        print(f"Error descargando precios (1d): {e}", flush=True)
    missing = [s for s in syms if s not in got]
    if missing:                                     # fin de semana / antes de abrir: últimos 5 días
        try:
            df = _download_close(missing, "5d")
            for s in missing:
                v = _last(df, s)
                if v:
                    got[s] = v
        except Exception as e:
            print(f"Error descargando precios (5d): {e}", flush=True)
    for s in [s for s in syms if s not in got]:     # último recurso: precio suelto
        try:
            lp = yf.Ticker(s).fast_info.get("lastPrice")
            if lp:
                got[s] = (datetime.now(timezone.utc), float(lp))
        except Exception as e:
            print(f"Sin precio para {s}: {e}", flush=True)
    now = time.time()
    with _lock:
        for p in pairs:
            if p in got:
                _fx[p[3:6]] = got[p][1]
        for t, m in metas.items():
            if t not in got:
                continue
            last_ts, price = got[t]
            _cache[t] = {"ticker": t, "name": m["name"], "currency": m["currency"],
                         "price": price, "prev_close": m["prev_close"], "ts": last_ts.isoformat(),
                         "updated": now}
    if got:
        _last_ok["t"] = now
    if len(got) < len(syms):
        print(f"Precios: {len(got)}/{len(syms)} conseguidos", flush=True)


def fresh(ticker):
    """Precio recién descargado (para ejecutar una operación simulada con el precio de verdad)."""
    ticker = ticker.upper()
    track([ticker])
    _refresh([ticker])
    with _lock:
        q = _cache.get(ticker)
    if not q or time.time() - q["updated"] > 120:
        return None
    return _with_eur(q)


def status():
    with _lock:
        n = len(_cache)
    return {"last_ok_s": int(time.time() - _last_ok["t"]) if _last_ok["t"] else None, "cached": n}


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


# ---------------------------------------------------------------- históricos para gráficas
RANGES = {  # rango -> (period de Yahoo, intervalo)
    "1d": ("1d", "5m"), "5d": ("5d", "30m"), "1mo": ("1mo", "1d"), "3mo": ("3mo", "1d"),
    "6mo": ("6mo", "1d"), "1y": ("1y", "1d"), "5y": ("5y", "1wk"), "max": ("max", "1mo"),
}
_hist_cache = {}  # (tickers, rango) -> (momento, DataFrame)


def history(tickers, rng="1mo"):
    """Cierres de varios valores para un rango (caché de 2 min intradía, 30 min diario)."""
    period, interval = RANGES.get(rng, RANGES["1mo"])
    key = (tuple(sorted(tickers)), rng)
    ttl = 120 if interval.endswith("m") else 1800
    hit = _hist_cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    df = yf.download(list(key[0]), period=period, interval=interval, progress=False, auto_adjust=True, threads=True)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(key[0][0])
    df = df.sort_index()
    _hist_cache[key] = (time.time(), df)
    return df


def series(ticker, rng="1mo"):
    df = history([ticker], rng)
    s = df[ticker].dropna() if ticker in df else pd.Series(dtype=float)
    return [{"t": int(ix.timestamp()), "v": round(float(v), 4)} for ix, v in s.items()]


SECTOR_ES = {"Technology": "Tecnología", "Financial Services": "Financiero", "Healthcare": "Salud",
             "Consumer Cyclical": "Consumo cíclico", "Consumer Defensive": "Consumo básico", "Industrials": "Industria",
             "Energy": "Energía", "Utilities": "Servicios públicos", "Real Estate": "Inmobiliario",
             "Communication Services": "Comunicaciones", "Basic Materials": "Materiales"}
_profiles = {}  # ticker -> (día, ficha)


def profile(ticker):
    """Ficha para medir el riesgo (se guarda un día): tipo, sector, beta, volatilidad de 1 año,
    rango de 52 semanas y precio objetivo. Si el valor está en el catálogo, trae lo que hay dentro del fondo."""
    import math
    today = datetime.now(timezone.utc).date()
    hit = _profiles.get(ticker)
    if hit and hit[0] == today:
        return hit[1]
    cat = catalog().get(ticker.upper(), {})
    info = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as e:
        print(f"Sin ficha de {ticker}: {e}", flush=True)
    qt = (info.get("quoteType") or "").upper()
    kind = {"Acción": "stock", "ETF": "etf", "ETC": "metal"}.get(cat.get("tipo_activo"), "stock" if qt == "EQUITY" else "etf" if qt else "stock")
    vol = None
    try:
        h = history([ticker], "1y")
        r = h[ticker].dropna().pct_change().dropna() if ticker in h else []
        if len(r) > 20:
            vol = float(r.std() * math.sqrt(252) * 100)
    except Exception:
        pass
    sector = SECTOR_ES.get(info.get("sector") or "", info.get("sector") or "")
    p = {"kind": kind, "sector": sector, "beta": info.get("beta") or cat.get("beta"),
         "vol": vol or cat.get("volatilidad"), "low52": info.get("fiftyTwoWeekLow"), "high52": info.get("fiftyTwoWeekHigh"),
         "target": info.get("targetMeanPrice") if kind == "stock" else None,
         "analysts": info.get("numberOfAnalystOpinions") if kind == "stock" else None,
         "issuers": cat.get("emisores"), "sectors": cat.get("sectores")}
    _profiles[ticker] = (today, p)
    return p


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
    now = time.time()
    q["stale_min"] = int((now - q.get("updated", now)) // 60)       # hace cuánto lo conseguimos
    try:
        q["age_min"] = int((datetime.now(timezone.utc) - datetime.fromisoformat(q["ts"])).total_seconds() // 60)
    except Exception:
        q["age_min"] = None
    # retraso típico según mercado (Yahoo gratis)
    q["realtime"] = not any(q["ticker"].endswith(s) for s in (".MC", ".DE", ".PA", ".AS", ".MI", ".L", ".T", ".SW", ".BR", ".LS"))
    return q


def snapshot(tickers):
    with _lock:
        return {t: _with_eur(_cache.get(t)) for t in tickers if _cache.get(t)}


# Bolsas principales primero (Yahoo devuelve antes cotizaciones secundarias como .NE, .TI, .HM…)
MAIN_SUFFIX = ["", ".MC", ".DE", ".PA", ".AS", ".MI", ".L", ".T", ".SW", ".BR", ".LS", ".HK", ".TO"]
OTC = {"PNK", "OQX", "OQB", "OTC", "OEM"}
_universe = None


def _local_universe():
    """Las ~780 empresas de los índices que analiza el informe, con su cotización principal."""
    global _universe
    if _universe is None:
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "data" / "universe.csv"
        try:
            _universe = pd.read_csv(path)[["ticker", "name", "market", "index"]].fillna("")
        except Exception:
            _universe = pd.DataFrame(columns=["ticker", "name", "market", "index"])
    return _universe


EUR_ETF_SUFFIX = (".DE", ".AS", ".MI", ".PA", ".MC")


def _rank(q):
    sym = q["symbol"]
    if q.get("exchange") in OTC:
        return len(MAIN_SUFFIX) + 1
    if q.get("quoteType") == "ETF" and sym.endswith(EUR_ETF_SUFFIX):   # fondos: mejor la cotización en euros
        return -1
    suf = "." + sym.split(".", 1)[1] if "." in sym else ""
    return MAIN_SUFFIX.index(suf) if suf in MAIN_SUFFIX else len(MAIN_SUFFIX)


ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_isin_map = None


def _isin_to_ticker():
    """ISIN -> ticker de las empresas del informe (caché que va rellenando el informe diario)."""
    global _isin_map
    if _isin_map is None:
        import json
        import os
        from pathlib import Path
        _isin_map = {}
        root = Path(__file__).resolve().parent.parent
        for f in (root / "data" / "isin.json", Path(os.environ.get("INFORME_DIR") or Path.home() / "inversiones-datos" / "informe").parent / "isin.json"):
            try:
                for tk, isin in json.loads(f.read_text()).items():
                    if isin:
                        _isin_map[isin.upper()] = tk
            except Exception:
                pass
    return _isin_map


_catalog = None


def catalog():
    """Fondos y valores conocidos: ISIN -> ficha (símbolo en euros, tipo, sectores y empresas de dentro)."""
    global _catalog
    if _catalog is None:
        import json
        from pathlib import Path
        try:
            items = json.loads((Path(__file__).resolve().parent.parent / "data" / "catalogo.json").read_text())["activos"]
        except Exception:
            items = []
        _catalog = {a["isin"].upper(): a for a in items}
        _catalog.update({a["yahoo_symbol"].upper(): a for a in items})
    return _catalog


def search(query):
    res, seen = [], set()
    cat = catalog().get(query.strip().upper())
    if cat:
        res.append({"ticker": cat["yahoo_symbol"], "name": cat["nombre"], "exchange": cat["tipo_activo"], "type": "ETF" if cat["tipo_activo"] != "Acción" else "EQUITY"})
        seen.add(cat["yahoo_symbol"])
    ql = query.lower().strip()
    if ISIN_RE.match(query.strip().upper()):   # buscar por ISIN (el código que enseña Trade Republic)
        tk = _isin_to_ticker().get(query.strip().upper())
        if tk:
            u = _local_universe()
            row = u[u["ticker"] == tk]
            res.append({"ticker": tk, "name": row["name"].iloc[0] if len(row) else tk, "exchange": "ISIN", "type": "EQUITY"})
            seen.add(tk)
    u = _local_universe()
    if len(u):
        m = u[u["name"].str.lower().str.contains(ql, regex=False) | (u["ticker"].str.lower() == ql)
              | u["ticker"].str.lower().str.startswith(ql + ".")]
        for _, r in m.head(5).iterrows():
            seen.add(r["ticker"])
            res.append({"ticker": r["ticker"], "name": r["name"], "exchange": r["index"], "type": "EQUITY"})
    try:
        quotes = [q for q in yf.Search(query, max_results=20).quotes
                  if q.get("quoteType") in ("EQUITY", "ETF") and q.get("symbol")]
    except Exception:
        quotes = []
    quotes.sort(key=_rank)
    for q in quotes:
        if q["symbol"] in seen:
            continue
        seen.add(q["symbol"])
        res.append({"ticker": q["symbol"], "name": " ".join((q.get("shortname") or q.get("longname") or "").split()),
                    "exchange": q.get("exchDisp") or q.get("exchange"), "type": q.get("quoteType")})
    return res[:12]


def _loop():
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
    pool = ThreadPoolExecutor(max_workers=2)
    while True:
        try:
            cutoff = time.time() - 3600  # deja de seguir lo que nadie mira en 1 h (salvo carteras, que se re-registran)
            with _lock:
                tickers = [t for t, ts in _tracked.items() if ts > cutoff]
            for i in range(0, len(tickers), 100):
                # vigilante: si Yahoo se cuelga, no se queda parado para siempre
                pool.submit(_refresh, tickers[i:i + 100]).result(timeout=90)
        except FutTimeout:
            print("Refresco de precios colgado más de 90 s: se reintenta", flush=True)
            pool = ThreadPoolExecutor(max_workers=2)
        except Exception as e:
            print("Error refrescando precios:", e, flush=True)
        time.sleep(REFRESH_SECONDS)


def start():
    threading.Thread(target=_loop, daemon=True, name="precios").start()
