"""Une el modelo de «Mi cartera» (modelo/v3.py, ~1.500 valores) con el informe diario de la app.

El modelo decide QUÉ empresas salen (Señal de compra, Rebote confirmado, Riesgo alto) y con qué nota.
El informe de siempre añade a cada una lo suyo: precio y gráfica de Yahoo, momento de entrada, noticias,
ISIN y las explicaciones sencillas del modo básico."""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

DATOS = Path(os.environ.get("INFORME_DIR") or Path.home() / "inversiones-datos" / "informe") / "modelo"

# zona del modelo -> mercado de la app
MARKET_LABEL = {"US": "EE. UU.", "ES": "España", "EU": "Europa", "JP": "Japón", "AS": "Asia"}
# Hoy y WhatsApp priorizan donde invertís (EE. UU. primero); Asia aporta muchos avisos de caída y va detrás
MARKET_WEIGHT = {"US": 1.0, "ES": 0.98, "EU": 0.97, "JP": 0.94, "AS": 0.85}

# bolsa de StockAnalysis -> sufijo de Yahoo
SUFIJO = {"bme": ".MC", "etr": ".DE", "epa": ".PA", "ams": ".AS", "bit": ".MI", "swx": ".SW", "lon": ".L", "cph": ".CO",
          "sto": ".ST", "ebr": ".BR", "hel": ".HE", "osl": ".OL", "lis": ".LS", "tyo": ".T", "tpe": ".TW", "krx": ".KS",
          "hkg": ".HK", "sha": ".SS", "she": ".SZ"}

SECTOR_ES = {"Healthcare": "Salud", "Consumer Staples": "Consumo básico", "Consumer Discretionary": "Consumo discrecional",
             "Financials": "Finanzas", "Technology": "Tecnología", "Industrials": "Industria", "Communication Services": "Comunicaciones",
             "Energy": "Energía", "Basic Materials": "Materiales", "Materials": "Materiales", "Utilities": "Eléctricas y servicios",
             "Real Estate": "Inmobiliario"}

# condición de compra -> frase corta (para chips y avisos)
CORTO = {"fuerza": "va mejor que su índice", "resultados": "sin resultados en 7 días", "tendencia": "tendencia de fondo",
         "giro": "giro a corto", "mercado": "mercado favorable", "nota": "atractivo de 70 o más", "valoracion": "valoración fiable",
         "datos": "datos recientes", "noticias": "sin noticias negativas", "calidadvalor": "calidad y valor",
         "caida": "caída desde máximos", "girorebote": "empieza a girarse", "mercadoalza": "su mercado ya sube",
         "panico": "sin pánico ni estrés", "notarebote": "nota de rebote"}


# país -> prefijos de ISIN aceptables (para buscarlo y enlazar con el bróker)
ISIN_PAIS = {"EE. UU.": ("US",), "España": ("ES",), "Japón": ("JP",), "Alemania": ("DE",), "Francia": ("FR",), "Países Bajos": ("NL",),
             "Italia": ("IT",), "Suiza": ("CH",), "Reino Unido": ("GB", "JE", "IE"), "Dinamarca": ("DK",), "Suecia": ("SE",),
             "Bélgica": ("BE",), "Finlandia": ("FI",), "Noruega": ("NO",), "Portugal": ("PT",), "Irlanda": ("IE",), "Austria": ("AT",),
             "China": ("CN",), "Taiwán": ("TW",), "Corea": ("KR",), "Hong Kong/China": ("HK", "KY", "BM", "CN")}


def yahoo(sa):
    """«bme/ITX» -> «ITX.MC», «BRK.B» -> «BRK-B», «hkg/0700» -> «0700.HK»."""
    if "/" not in sa:
        return sa.replace(".", "-")
    ex, s = sa.split("/", 1)
    return s.replace(".", "-") + SUFIJO.get(ex, "")


def market(x):
    p, r = x.get("pais"), x.get("region")
    if p == "Japón":
        return "JP"
    if r == "Asia":
        return "AS"
    return {"EE. UU.": "US", "España": "ES"}.get(r, "EU")


def _load(name):
    p = DATOS / name
    return json.loads(p.read_text()) if p.exists() else None


def load(today=None, max_days=4):
    """Las dos listas del modelo si son recientes (de hoy o de los últimos días); si no, None."""
    o, r = _load("oportunidades.json"), _load("caidas.json")
    if not o or not r:
        return None
    today = today or date.today()
    try:
        if date.fromisoformat(o["fecha"]) < today - timedelta(days=max_days):
            return None
    except Exception:
        return None
    return o, r


def _frases(motivo):
    """«A favor: a; b; c.» -> ["A", "B", "C"]"""
    t = re.sub(r"^[^:]{0,40}:\s*", "", motivo or "").rstrip(".")
    return [s.strip()[:1].upper() + s.strip()[1:] for s in t.split(";") if s.strip()]


def plain_risk(s):
    """Señal de riesgo del modelo explicada para alguien sin experiencia."""
    m = re.search(r"tendencia bajista \((\d+) % bajo", s, re.I)
    if m:
        return f"Lleva meses bajando: está un {m.group(1)} % por debajo de su precio medio de los últimos 10 meses."
    low = s.lower()
    if "momento" in low:
        return "En el último año ha ido peor que casi todas las demás."
    if "calidad baja" in low:
        return "Gana poco dinero para lo que tiene o va muy endeudada."
    if "cara" in low:
        return "Cuesta mucho para lo que gana, comparada con las de su sector."
    if "cortos" in low or "emisión" in low:
        return "Hay muchos inversores apostando a que baja, o la empresa saca acciones nuevas."
    if "altman" in low:
        return "Sus cuentas muestran un riesgo financiero alto."
    return ""


def model_info(x, kind):
    """Lo que la app enseña del modelo en el detalle de cada empresa."""
    e = x.get("entrada") or {}
    return {
        "kind": kind, "estado": x.get("estado"), "nota": x.get("puntuacion"), "atractivo": x.get("atractivo"),
        "bloques": x.get("senales"), "pesos": x.get("pesos"), "motivo": x.get("motivo"), "tags": x.get("tags"),
        "tendencia": x.get("regimen"), "confianza": x.get("confianza"), "mantiene": x.get("mantiene"),
        "stop": x.get("stop"), "d200": x.get("d200"), "resultadosEn": x.get("resultadosEn"),
        "condiciones": [dict(c, corto=CORTO.get(c["clave"], c["clave"])) for c in e.get("condiciones", [])],
        "cumple": e.get("cumple"), "total": e.get("total"), "rebote": x.get("rebote"),
        "recorrido": x.get("recorrido"), "revisiones": x.get("revisiones"), "fecha": x.get("fechaDatos"),
        "pais": x.get("pais"), "bolsa": x.get("mercado"), "sa": x.get("sa"), "consenso": x.get("consenso"),
    }


def base_record(x, kind):
    """Registro con los campos que usa la app; precio y técnicos se completan luego con Yahoo."""
    mk = market(x)
    flags = []
    if x.get("resultadosEn") is not None and 0 <= x["resultadosEn"] <= 14:
        flags.append(f"Presenta resultados en {x['resultadosEn']} d: puede moverse mucho")
    if kind == "rebote":
        flags.append("Señal experimental: más riesgo que una señal de compra normal")
    rec = {
        "ticker": yahoo(x["sa"]), "sa": x["sa"], "name": x["nombre"], "short": re.sub(r",? (S\.A\.|Inc\.?|Corporation|Co\., Ltd\.|Ltd\.|AG|SE|plc)$", "", x["nombre"]),
        "market": mk, "market_label": MARKET_LABEL[mk], "index": x.get("mercado") or "", "sector": SECTOR_ES.get(x.get("sector"), x.get("sector") or ""),
        "currency": x.get("divisa") or "", "score": x.get("puntuacion"), "rank_score": round((x.get("puntuacion") or 0) * MARKET_WEIGHT[mk], 1),
        "blocks": {}, "reasons": _frases(x.get("motivo")), "flags": flags, "coverage": 1,
        "upside": (x["potencial"] / 100) if x.get("potencial") is not None else None, "pe": None, "roe": None,
        "target": x.get("objetivo"), "analysts": x.get("nAnalistas") or None,
        "price": x.get("precio"), "chg1d": None, "chg1m": None, "spark": [],
        "isin_prefix": ISIN_PAIS.get(x.get("pais")) or ("US",),
        "model": model_info(x, kind),
    }
    if kind == "riesgo":
        sig = rec["reasons"] or ["Tendencia bajista"]
        rec["risk"] = {"score": x.get("puntuacion"), "level": "alta", "signals": sig, "plain": [plain_risk(s) for s in sig], "flags": flags}
        rec["score"] = None   # la nota de oportunidad no viene en la lista de riesgo
    return rec


def lists(o, r, top_n=10, per_market=15):
    """Selección de empresas: compras (todas), rebotes (todos) y riesgo alto (las más relevantes)."""
    buy = [base_record(x, "compra") for x in o["items"] if x.get("estado") == "Señal de compra"]
    reb = [base_record(x, "rebote") for x in o["items"] if x.get("estado") == "Rebote confirmado"]
    risk = [base_record(x, "riesgo") for x in r["items"] if x.get("estado") == "Riesgo alto"]
    buy.sort(key=lambda z: -z["score"])
    reb.sort(key=lambda z: -z["score"])
    risk.sort(key=lambda z: -z["rank_score"])
    by_market = {m: [z for z in buy if z["market"] == m] for m in MARKET_LABEL}
    risk_by_market = {m: [z for z in risk if z["market"] == m][:per_market] for m in MARKET_LABEL}
    return buy, reb, risk[:top_n], risk_by_market, by_market, len(risk)


def summary(o, r):
    """Resumen del modelo para la app: estado de cada mercado, notas de lectura y listas cercanas."""
    return {
        "fecha": o.get("fecha"), "version": o.get("version"), "universo": o.get("universo"), "fuente": o.get("fuenteDatos"),
        "regimen": o.get("regimen"), "nota_compra": o.get("nota"), "nota_riesgo": r.get("nota"),
        "concentracion": o.get("concentracion"),
        "esperar": [dict(e, market=market({"region": e.get("region"), "pais": None})) for e in (o.get("extras") or [])][:40],
        "riesgo_cerca": len(r.get("extras") or []),
    }
