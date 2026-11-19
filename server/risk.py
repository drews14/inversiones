"""Riesgo de una cartera: concentración, sector, volatilidad (escala 1-7) y sensibilidad al mercado.

Adaptado del módulo «Mi cartera» (portfolio.py, calcular_riesgos). Mira dentro de los fondos del catálogo
(data/catalogo.json) para saber cuánto dependes de verdad de cada empresa y de cada sector.
"""
import math
import re

from . import prices

NIVELES = ["Bueno", "Moderado", "Medio", "Alto", "Severo"]
CORTES = {"conc": [10, 20, 30, 50], "sec": [20, 30, 45, 60], "beta": [0.6, 0.85, 1.1, 1.4]}
SRI_CORTES = [0.5, 5, 12, 20, 30, 80]   # escala CNMV/PRIIPs (volatilidad anual %)
SRI_A_NIVEL = [0, 0, 0, 1, 2, 3, 4, 4]
DEF_VOL = {"stock": 30.0, "etf": 16.0, "metal": 20.0}
DEF_BETA = {"stock": 1.1, "etf": 1.0, "metal": 0.3}


def _nivel(v, cortes):
    return sum(v >= c for c in cortes)


def _sri(vol):
    return next((k + 1 for k, t in enumerate(SRI_CORTES) if vol < t), 7)


def _corr(a, b):
    if a is b:
        return 1.0
    s = {a["kind"], b["kind"]}
    if s == {"metal"}:
        return 0.8
    if "metal" in s:
        return 0.1
    if s == {"etf"}:
        return 0.85
    if s == {"stock"}:
        return 0.55
    return 0.7


def _f(v, d=0):
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


SUFIJOS = re.compile(r"[,.]?\s+(corporation|corp\.?|inc\.?|incorporated|plc|s\.a\.?|sa|ltd\.?|limited|co\.?|ag|se|n\.v\.?|holdings?|group)$", re.I)


def _clean(n):
    n = (n or "").strip()
    for _ in range(3):
        n = SUFIJOS.sub("", n).strip()
    return n


def _merge(acc, name, v):
    """Suma por empresa: «NVIDIA Corporation» (directa) y «NVIDIA» (dentro de un fondo) son la misma."""
    key = _clean(name).lower()
    for k in acc:
        if k == key or k.startswith(key + " ") or key.startswith(k + " "):
            acc[k][1] += v
            return
    acc[key] = [_clean(name), v]


def portfolio_risk(positions):
    """positions: las de portfolio.compute (ticker, name, value_eur). Devuelve indicadores y fichas."""
    L = [p for p in positions if (p.get("value_eur") or 0) > 0]
    if not L:
        return None
    tot = sum(p["value_eur"] for p in L)
    rows = []
    for p in L:
        pr = prices.profile(p["ticker"])
        name = _clean((p.get("name") or p["ticker"]).split(",")[0])
        rows.append({"t": p["ticker"], "name": name, "w": p["value_eur"] / tot, "pr": pr,
                     "vol": pr.get("vol") or DEF_VOL[pr["kind"]], "beta": pr.get("beta") if pr.get("beta") is not None else DEF_BETA[pr["kind"]],
                     "est": pr.get("vol") is None or pr.get("beta") is None})
    out = {}

    # 1) Concentración por empresa (directa + dentro de los fondos)
    acc = {}
    for r in sorted(rows, key=lambda r: r["pr"]["kind"] == "etf"):   # primero las directas: dan el nombre
        inside = r["pr"].get("issuers") or ({r["name"]: 1} if r["pr"]["kind"] != "etf" else {})
        for n, f in inside.items():
            _merge(acc, n, r["w"] * float(f) * 100)
    iss = {n: v for n, v in acc.values()}
    if iss:
        n, v = max(iss.items(), key=lambda x: x[1])
        out["conc"] = {"label": "Concentración", "nivel": _nivel(v, CORTES["conc"]), "value": f"{_f(v)} %",
                       "text": f"El {_f(v)} % de tu dinero depende de {n}.",
                       "top": [{"n": k, "v": round(x, 1)} for k, x in sorted(iss.items(), key=lambda x: -x[1])[:5]]}

    # 2) Sector principal (mirando dentro de los fondos)
    sec = {}
    for r in rows:
        inside = r["pr"].get("sectors") or ({r["pr"]["sector"]: 1} if r["pr"].get("sector") else {})
        for n, f in inside.items():
            if n.lower() not in ("otros", "sin clasificar"):
                sec[n] = sec.get(n, 0) + r["w"] * float(f) * 100
    if sec:
        n, v = max(sec.items(), key=lambda x: x[1])
        out["sec"] = {"label": "Sector", "nivel": _nivel(v, CORTES["sec"]), "value": f"{_f(v)} %",
                      "text": f"El {_f(v)} % está en {n.lower()}. Si ese sector cae, cae casi toda tu cartera." if v >= 45 else f"El sector con más peso es {n.lower()} ({_f(v)} %).",
                      "top": [{"n": k, "v": round(x, 1)} for k, x in sorted(sec.items(), key=lambda x: -x[1])[:5]]}

    # 3) Volatilidad con correlaciones -> escala 1 a 7
    var = sum(a["w"] * b["w"] * a["vol"] * b["vol"] * _corr(a["pr"], b["pr"]) for a in rows for b in rows)
    vol = math.sqrt(var)
    k = _sri(vol)
    month = tot * vol / math.sqrt(12) / 100
    out["vol"] = {"label": "Volatilidad", "nivel": SRI_A_NIVEL[k], "value": f"{k} de 7",
                  "text": f"Se mueve en torno a un {_f(vol)} % al año: en un mes normal tu dinero invertido puede subir o bajar unos {_f(month)} €."}

    # 4) Sensibilidad al mercado (beta media)
    b = sum(r["w"] * r["beta"] for r in rows)
    out["beta"] = {"label": "Sensibilidad al mercado", "nivel": _nivel(b, CORTES["beta"]), "value": _f(b, 2),
                   "text": f"Si la bolsa baja un 10 %, tu cartera tiende a bajar un {_f(b * 10)} %." if b >= 0.3
                   else "Se mueve poco con la bolsa en general."}

    lv = [out[k]["nivel"] for k in ("conc", "sec", "vol", "beta") if k in out]
    g = int(math.floor(sum(lv) / len(lv) + 0.5))
    for k in ("conc", "sec", "vol", "beta"):
        if k in out:
            out[k]["nivel_name"] = NIVELES[out[k]["nivel"]]
    profiles = {r["t"]: {k: r["pr"].get(k) for k in ("low52", "high52", "target", "analysts", "sector", "kind")} for r in rows}
    return {"global": {"nivel": g, "name": NIVELES[g]}, "items": [out[k] for k in ("conc", "sec", "vol", "beta") if k in out],
            "estimated": [r["name"] for r in rows if r["est"]], "profiles": profiles}
