"""Screener diario de oportunidades de compra.

Genera docs/data/report.json (lo lee la web app) y envía una notificación por ntfy.
Uso:  python screener/run.py [--limit N] [--no-notify] [--force]
"""
import argparse
import io
import json
import math
import re
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
import config as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data"
TZ = ZoneInfo("Europe/Madrid")


# ---------------------------------------------------------------- utilidades
def clamp01(x):
    return max(0.0, min(1.0, x))


def num(v):
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def rsi(series, n=14):
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def clean(o):
    """Convierte NaN/inf en None para que el JSON sea válido."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


# ---------------------------------------------------------------- datos
def load_prices(tickers):
    """Descarga 1 año de cierres diarios de todos los tickers en bloque."""
    frames = []
    for i in range(0, len(tickers), 200):
        chunk = tickers[i:i + 200]
        df = yf.download(chunk, period="1y", interval="1d", auto_adjust=True,
                         progress=False, threads=True, group_by="column")["Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame(chunk[0])
        frames.append(df)
    return pd.concat(frames, axis=1)


def load_info(ticker):
    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).info or {}
            if info.get("regularMarketPrice") or info.get("currentPrice") or attempt == 2:
                return ticker, info
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return ticker, {}


def load_infos(tickers):
    with ThreadPoolExecutor(max_workers=8) as ex:
        infos = dict(ex.map(load_info, tickers))
    # Yahoo limita la velocidad: reintenta despacio las que vinieron vacías
    missing = [t for t, i in infos.items() if not i.get("regularMarketPrice") and not i.get("currentPrice")]
    if missing:
        print(f"Reintentando {len(missing)} sin datos…")
        time.sleep(20)
        with ThreadPoolExecutor(max_workers=2) as ex:
            infos.update({t: i for t, i in ex.map(load_info, missing) if i})
    return infos


def technicals(close):
    close = close.dropna()
    if len(close) < 60:
        return None
    price = close.iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.mean()
    sma50 = close.rolling(50).mean().iloc[-1]
    hi52 = close.max()
    return {
        "price": float(price),
        "chg1d": float(close.iloc[-1] / close.iloc[-2] - 1),
        "chg1m": float(close.iloc[-1] / close.iloc[-22] - 1) if len(close) > 22 else None,
        "rsi": float(rsi(close).iloc[-1]),
        "sma50": float(sma50),
        "sma200": float(sma200),
        "vs_sma200": float(price / sma200 - 1),
        "drawdown": float(price / hi52 - 1),
        "spark": [round(float(x), 2) for x in close.iloc[-60:].tolist()],
    }


# ---------------------------------------------------------------- puntuación
def score(t, info, sector_pe):
    """Devuelve (bloques, motivos, alertas, cobertura). Cada bloque 0..1."""
    reasons, flags = [], []
    have, total = 0, 0

    def track(v):
        nonlocal have, total
        total += 1
        if v is not None:
            have += 1
        return v

    # --- Valoración
    v = 0.0
    pe = track(num(info.get("forwardPE")) or num(info.get("trailingPE")))
    med = sector_pe.get(info.get("sector"))
    if pe and pe > 0 and med:
        r = pe / med
        v += clamp01((1.2 - r) / 0.7) * 0.4
        if r < 0.8:
            reasons.append(f"PER {pe:.1f} vs {med:.1f} de su sector ({(1 - r) * 100:.0f}% más barata)")
    peg = track(num(info.get("trailingPegRatio")) or num(info.get("pegRatio")))
    if peg and peg > 0:
        v += (0.32 if peg < 1 else 0.2 if peg < 1.5 else 0.08 if peg < 2 else 0)
        if peg < 1:
            reasons.append(f"PEG {peg:.2f} (crecimiento barato)")
    fcf, mcap = num(info.get("freeCashflow")), num(info.get("marketCap"))
    fcfy = track(fcf / mcap if fcf and mcap else None)
    if fcfy is not None:
        v += clamp01(fcfy / 0.08) * 0.28
        if fcfy >= 0.06:
            reasons.append(f"Rentabilidad por flujo de caja libre {fcfy * 100:.1f}%")

    # --- Técnico
    te = 0.0
    te += clamp01((40 - t["rsi"]) / 15) * 0.4
    if t["rsi"] < 32:
        reasons.append(f"RSI {t['rsi']:.0f}: sobreventa")
    te += clamp01((-t["drawdown"] - 0.05) / 0.25) * 0.32
    if t["drawdown"] < -0.2:
        reasons.append(f"{t['drawdown'] * 100:.0f}% desde máximos de 52 semanas")
    te += clamp01(-t["vs_sma200"] / 0.15) * 0.28
    if t["chg1m"] is not None and t["chg1m"] < -0.25:
        flags.append("Caída >25% en un mes: posible «cuchillo cayendo», espera estabilización")

    # --- Calidad / fiabilidad
    q = 0.0
    roe = track(num(info.get("returnOnEquity")))
    if roe is not None:
        q += clamp01(roe / 0.20) * 0.32
        if roe >= 0.2:
            reasons.append(f"ROE {roe * 100:.0f}%")
    de = track(num(info.get("debtToEquity")))
    if info.get("sector") == "Financial Services":
        q += 0.14  # el apalancamiento de bancos no es comparable
    elif de is not None:
        q += clamp01((200 - de) / 150) * 0.28
        if de > 250:
            flags.append(f"Deuda elevada (deuda/patrimonio {de:.0f}%)")
    pm = track(num(info.get("profitMargins")))
    if pm is not None:
        q += clamp01(pm / 0.15) * 0.2
        if pm < 0:
            flags.append("Pierde dinero (margen neto negativo)")
    eg = track(num(info.get("earningsGrowth")))
    if eg is not None:
        q += clamp01(eg / 0.2) * 0.2

    # --- Analistas
    a = 0.0
    tgt = track(num(info.get("targetMeanPrice")))
    nan_ = num(info.get("numberOfAnalystOpinions")) or 0
    upside = tgt / t["price"] - 1 if tgt and t["price"] else None
    if upside is not None:
        a += clamp01(upside / 0.30) * 0.48
        if upside > 0.2 and nan_ >= 5:
            reasons.append(f"Potencial {upside * 100:.0f}% al precio objetivo ({int(nan_)} analistas)")
    rec = track(num(info.get("recommendationMean")))
    if rec:
        a += clamp01((3 - rec) / 2) * 0.36
    a += clamp01(nan_ / 5) * 0.16

    blocks = {"valuation": v, "technical": te, "quality": q, "analysts": a}
    if q < 0.35 and v > 0.6:
        flags.append("Barata pero de baja calidad: posible trampa de valor")
    ets = num(info.get("earningsTimestamp"))
    if ets:
        days = (datetime.fromtimestamp(ets, timezone.utc) - datetime.now(timezone.utc)).days
        if 0 <= days <= 14:
            flags.append(f"Presenta resultados en {days} días (más volatilidad)")
    return blocks, reasons, flags, (have / total if total else 0), upside, pe, roe


# ---------------------------------------------------------------- macro y noticias
def macro_panel():
    tick = list(C.MARKET_PANEL)
    df = yf.download(tick, period="1mo", interval="1d", progress=False, auto_adjust=False)["Close"]
    out = []
    for k, label in C.MARKET_PANEL.items():
        s = df[k].dropna() if k in df else pd.Series(dtype=float)
        if len(s) < 2:
            continue
        out.append({"ticker": k, "label": label, "value": round(float(s.iloc[-1]), 2),
                    "chg1d": float(s.iloc[-1] / s.iloc[-2] - 1),
                    "chg1m": float(s.iloc[-1] / s.iloc[0] - 1)})
    return out


def fred():
    out = []
    for sid, meta in C.FRED_SERIES.items():
        try:
            txt = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=30,
                               headers={"User-Agent": "screener-bot/1.0"}).text
            s = pd.read_csv(io.StringIO(txt), index_col=0, parse_dates=True).iloc[:, 0]
            s = pd.to_numeric(s, errors="coerce").dropna()
            daily = len(s) > 2 and (s.index[-1] - s.index[-2]).days < 7
            if daily:
                last = s.iloc[-1:]
                s = pd.concat([s.resample("MS").last().iloc[:-1], last])
            if meta["yoy"]:
                s = (s / s.shift(12) - 1) * 100
                s = s.dropna()
            out.append({"id": sid, "label": meta["label"], "value": round(float(s.iloc[-1]), 2),
                        "prev": round(float(s.iloc[-2]), 2), "date": s.index[-1].strftime("%d/%m/%Y" if daily else "%Y-%m"),
                        "history": [round(float(x), 2) for x in s.iloc[-24:]]})
        except Exception as e:
            print("FRED error", sid, e)
    d = {x["id"]: x for x in out}
    es, de = d.get("IRLTLT01ESM156N"), d.get("IRLTLT01DEM156N")
    if es and de:
        out.append({"id": "SPREAD_ES", "label": "Prima de riesgo España (pb)",
                    "value": round((es["value"] - de["value"]) * 100), "prev": round((es["prev"] - de["prev"]) * 100),
                    "date": es["date"], "history": [round((a - b) * 100) for a, b in zip(es["history"], de["history"])]})
    return out


def sentiment(prices, uni, markets):
    """Termómetro propio 0-100 (0 = pánico, 100 = euforia) a partir de la amplitud del S&P 500 y el VIX."""
    sp = [t for t in uni[uni["index"].str.contains("S&P 500")]["ticker"] if t in prices]
    px = prices[sp].dropna(how="all", axis=1).dropna(how="all").ffill()
    last = px.iloc[-1]
    above200 = float((last > px.rolling(200, min_periods=150).mean().iloc[-1]).mean() * 100)
    above50 = float((last > px.rolling(50).mean().iloc[-1]).mean() * 100)
    vix = next((m["value"] for m in markets if m["ticker"] == "^VIX"), None)
    vix_score = clamp01((35 - vix) / 23) * 100 if vix else 50
    value = round(0.4 * above200 + 0.3 * above50 + 0.3 * vix_score)
    label = ("Miedo extremo" if value < 25 else "Miedo" if value < 45 else "Neutral" if value < 55
             else "Codicia" if value < 75 else "Codicia extrema")
    return {"value": value, "label": label, "above200": round(above200, 1), "above50": round(above50, 1),
            "vix": vix, "note": "Con miedo en el mercado suele haber más oportunidades, pero también más riesgo."}


GNEWS_LANG = {"es": "hl=es&gl=ES&ceid=ES:es", "en": "hl=en-US&gl=US&ceid=US:en"}


def news_for(query, n, lang="en"):
    """Titulares recientes desde Google News RSS (gratis, sin clave)."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    from urllib.parse import quote_plus
    try:
        r = requests.get(f"https://news.google.com/rss/search?q={quote_plus(query)}+when:3d&{GNEWS_LANG[lang]}",
                         timeout=20)
        out = []
        for it in ET.fromstring(r.content).findall(".//item")[:n]:
            title = it.findtext("title") or ""
            src = it.findtext("source") or ""
            if src and title.endswith(" - " + src):
                title = title[: -len(src) - 3]
            d = it.findtext("pubDate")
            out.append({"title": title, "publisher": src, "url": it.findtext("link"),
                        "date": parsedate_to_datetime(d).isoformat() if d else None})
        return out
    except Exception as e:
        print("news error", query, e)
        return []


def company_news(r):
    lang = "es" if r["market"] == "ES" else "en"
    name = str(r["name"]).split(",")[0]
    return news_for(f'"{name}" stock' if lang == "en" else f'"{name}" bolsa', C.NEWS_PER_TICKER, lang)


# ---------------------------------------------------------------- ISIN (para enlazar con el bróker)
ISIN_CACHE = ROOT / "data" / "isin.json"
ISIN_PREFIX = {"ES": ("ES",), "JP": ("JP",), "US": ("US",)}


def isin_ok(code):
    """Valida el dígito de control de un ISIN."""
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", code or ""):
        return False
    digits = "".join(str(int(ch, 36)) for ch in code[:-1])
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(code[-1])


def load_isin_cache():
    try:
        return json.loads(ISIN_CACHE.read_text())
    except Exception:
        return {}


def save_isin_cache(cache):
    ISIN_CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True))


def find_isin(r, cache):
    tk = r["ticker"]
    if tk in cache:
        return cache[tk]
    from urllib.parse import quote
    name = re.sub(r"[,.]|\b(Inc|Corp|Corporation|Co|Ltd|plc|S\.?A|N\.?V|Holdings?|Group)\b", " ", str(r["name"]))
    name = " ".join(name.split()[:3])
    base = tk.split(".")[0].upper()
    found = None
    try:
        txt = requests.get("https://markets.businessinsider.com/ajax/SearchController_Suggest?max_results=25&query="
                           + quote(name), timeout=15).text
        entries = re.findall(r'new Array\("([^"]*)", "Stocks", "([^"]*)"', txt)
        good = []
        for _, kw in entries:
            parts = kw.split("|")
            if len(parts) > 1 and parts[1][:2] in ISIN_PREFIX[r["market"]] and isin_ok(parts[1]):
                good.append(parts)
        # preferimos la que coincide con el ticker; si no, la primera del país correcto
        exact = [p for p in good if base in (p[0].upper(), p[-1].upper())]
        found = (exact or good or [[None, None]])[0][1]
    except Exception as e:
        print("ISIN error", tk, e)
    if found:
        cache[tk] = found
    return found


# ---------------------------------------------------------------- notificación
def notify(report):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("NTFY_TOPIC no definido: no se envía notificación")
        return
    top = report["top"][:3]
    lines = [f"{o['ticker']} {o['score']:.0f}/100 · {o['name']}" for o in top] or ["Hoy no hay oportunidades claras."]
    m = {x["id"]: x for x in report["macro"]}
    if "CPIAUCSL" in m:
        lines.append(f"IPC EE. UU.: {m['CPIAUCSL']['value']}%")
    vix = next((x for x in report["markets"] if x["ticker"] == "^VIX"), None)
    if vix:
        lines.append(f"VIX: {vix['value']}")
    headers = {"Title": f"Informe {report['date_label']}: {len(report['top'])} oportunidades",
               "Tags": "chart_with_upwards_trend"}
    if os.environ.get("APP_URL"):
        headers["Click"] = os.environ["APP_URL"]
    requests.post(f"https://ntfy.sh/{topic}", data="\n".join(lines).encode(), headers=headers, timeout=30)
    print("Notificación enviada")


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="analizar solo N empresas (pruebas)")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignorar la comprobación de hora")
    args = ap.parse_args()

    now = datetime.now(TZ)
    # GitHub Actions lanza en UTC: hay dos crons (verano/invierno) y solo sigue el que cae a las 7h de Madrid.
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not args.force:
        if now.hour not in (7, 8):  # 8 por si GitHub llega con retraso
            print(f"Son las {now:%H:%M} en Madrid: este cron no toca hoy.")
            return
        if (OUT / "history" / f"{now:%Y-%m-%d}.json").exists():
            print("El informe de hoy ya está generado.")
            return

    uni = pd.read_csv(ROOT / "data" / "universe.csv")
    if args.limit:
        uni = pd.concat([g.head(args.limit) for _, g in uni.groupby("market")])
    tickers = uni["ticker"].tolist()
    print(f"Analizando {len(tickers)} empresas…")

    prices = load_prices(tickers)
    infos = load_infos(tickers)

    # PER mediano por sector (para comparar cada empresa con sus pares)
    pes = pd.DataFrame([{"sector": i.get("sector"), "pe": num(i.get("forwardPE")) or num(i.get("trailingPE"))}
                        for i in infos.values()]).dropna()
    pes = pes[(pes.pe > 0) & (pes.pe < 150)]
    sector_pe = pes.groupby("sector")["pe"].median().to_dict()

    rows = []
    for _, u in uni.iterrows():
        tk = u["ticker"]
        if tk not in prices:
            continue
        t = technicals(prices[tk])
        info = infos.get(tk, {})
        if not t or not info:
            continue
        blocks, reasons, flags, cov, upside, pe, roe = score(t, info, sector_pe)
        if cov < C.MIN_DATA_COVERAGE:
            continue
        total = sum(blocks[k] * C.WEIGHTS[k] for k in blocks)
        rows.append({
            "ticker": tk, "name": info.get("shortName") or u["name"], "market": u["market"],
            "market_label": C.MARKET_LABEL[u["market"]], "index": u["index"],
            "sector": info.get("sector") or u.get("sector") or "", "currency": info.get("currency", ""),
            "score": round(total, 1), "rank_score": round(total * C.MARKET_WEIGHT[u["market"]], 1),
            "blocks": {k: round(blocks[k] * C.WEIGHTS[k], 1) for k in blocks},
            "reasons": reasons, "flags": flags, "coverage": round(cov, 2),
            "upside": upside, "pe": pe, "roe": roe,
            "recommendation": info.get("recommendationKey"), "analysts": info.get("numberOfAnalystOpinions"),
            **{k: t[k] for k in ("price", "chg1d", "chg1m", "rsi", "vs_sma200", "drawdown", "spark")},
        })

    df = pd.DataFrame(rows).sort_values("rank_score", ascending=False)
    cand = df[df.score >= C.MIN_SCORE]
    top = cand.head(C.TOP_GLOBAL)
    by_market = {m: cand[cand.market == m].head(C.TOP_PER_MARKET).to_dict("records") for m in C.MARKET_WEIGHT}

    top_records = top.to_dict("records")
    # Noticias e ISIN para todas las empresas que se muestran (top + cada mercado)
    isins = load_isin_cache()
    shown = {}
    for r in top_records + [x for v in by_market.values() for x in v]:
        if r["ticker"] not in shown:
            shown[r["ticker"]] = {"news": company_news(r), "isin": find_isin(r, isins)}
        r.update(shown[r["ticker"]])
    save_isin_cache(isins)

    markets = macro_panel()
    report = {
        "generated_at": now.isoformat(),
        "date_label": now.strftime("%d/%m/%Y"),
        "universe_size": len(tickers),
        "analyzed": len(df),
        "candidates": len(cand),
        "weights": C.WEIGHTS,
        "market_weight": C.MARKET_WEIGHT,
        "markets": markets,
        "sentiment": sentiment(prices, uni, markets),
        "macro": fred(),
        "market_news": {k: news_for(q, 5, lang) for k, (q, lang) in C.MARKET_NEWS.items()},
        "top": top_records,
        "by_market": by_market,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "history").mkdir(exist_ok=True)
    js = json.dumps(clean(report), ensure_ascii=False, default=str, allow_nan=False)
    (OUT / "report.json").write_text(js)
    (OUT / "history" / f"{now:%Y-%m-%d}.json").write_text(js)
    days = sorted(p.stem for p in (OUT / "history").glob("20*.json"))
    for old_day in days[:-60]:  # conserva solo los últimos 60 informes
        (OUT / "history" / f"{old_day}.json").unlink()
    idx = days[-60:]
    (OUT / "history" / "index.json").write_text(json.dumps(idx))
    print(f"OK: {len(df)} analizadas, {len(cand)} candidatas. Top: {', '.join(top.ticker.head(5))}")

    if not args.no_notify:
        notify(report)


if __name__ == "__main__":
    main()
