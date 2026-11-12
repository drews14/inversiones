"""Descarga las listas de componentes de los índices y las guarda en data/universe.csv.
Ejecutar de vez en cuando (p. ej. mensual) para refrescar los índices."""
import io
import re
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) screener-bot"}


def _tables(url):
    html = requests.get(url, headers=UA, timeout=30).text
    return pd.read_html(io.StringIO(html))


def sp500():
    t = _tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    return pd.DataFrame({"ticker": t["Symbol"].str.replace(".", "-", regex=False),
                         "name": t["Security"], "sector": t["GICS Sector"], "market": "US", "index": "S&P 500"})


def nasdaq100():
    for t in _tables("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"):
        cols = [c for c in t.columns if str(c).lower() in ("ticker", "symbol")]
        if cols and len(t) > 90:
            name_col = "Company" if "Company" in t.columns else t.columns[0]
            sec = next((c for c in t.columns if "Sector" in str(c) or "Industry" in str(c)), None)
            return pd.DataFrame({"ticker": t[cols[0]].str.replace(".", "-", regex=False), "name": t[name_col],
                                 "sector": t[sec] if sec else "", "market": "US", "index": "Nasdaq 100"})
    raise RuntimeError("Nasdaq-100 table not found")


def ibex35():
    for t in _tables("https://en.wikipedia.org/wiki/IBEX_35"):
        if "Ticker" in t.columns and len(t) >= 30:
            sec = next((c for c in t.columns if "Sector" in str(c)), None)
            return pd.DataFrame({"ticker": t["Ticker"].astype(str).str.strip(), "name": t["Company"],
                                 "sector": t[sec] if sec else "", "market": "ES", "index": "IBEX 35"})
    raise RuntimeError("IBEX table not found")


def nikkei225():
    """Componentes del Nikkei 225 desde la lista de Wikipedia (cada <li> lleva el código TSE)."""
    import html as _html
    h = requests.get("https://en.wikipedia.org/wiki/Nikkei_225", headers=UA, timeout=30).text
    rows, seen = [], set()
    for li in re.findall(r"<li[^>]*>(.*?)</li>", h, flags=re.S):
        m = re.search(r"topSearchStr=(\w{4})", li)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        name = _html.unescape(re.sub(r"<[^>]+>", "", li)).split(" (")[0].strip()
        rows.append({"ticker": f"{m.group(1)}.T", "name": name, "sector": "",
                     "market": "JP", "index": "Nikkei 225"})
    if len(rows) < 200:
        raise RuntimeError(f"Nikkei: only {len(rows)} rows")
    return pd.DataFrame(rows)


if __name__ == "__main__":
    frames = []
    for fn in (sp500, nasdaq100, ibex35, nikkei225):
        try:
            df = fn()
            print(fn.__name__, len(df))
            frames.append(df)
        except Exception as e:
            print("ERROR", fn.__name__, e)
    u = pd.concat(frames)
    # Un ticker del S&P y del Nasdaq a la vez: conservamos ambos índices en una columna
    u = u.groupby("ticker", as_index=False).agg({"name": "first", "sector": "first", "market": "first",
                                                  "index": lambda s: " / ".join(sorted(set(s)))})
    u.to_csv("data/universe.csv", index=False)
    print("total", len(u))
