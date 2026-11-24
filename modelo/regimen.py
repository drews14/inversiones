"""Régimen de mercado con datos (sustituye al termómetro manual en la condición «mercado»).
Fuentes gratuitas: FRED (S&P 500 y Nikkei 225 diarios, VIX, NFCI de la Fed de Chicago, diferencial high yield ICE BofA)
y la amplitud de cada zona calculada con las fichas del día (fichas3.json): % de valores sobre su media de 200 y de 50.
Regla por zona (documentada en claude/mercado-riesgo-caida.md):
  tendencia OK  = índice sobre su media de 200 sesiones (EE. UU., Japón) o, donde no hay índice gratuito, ≥ 50 % de valores sobre su media de 200
  sin estrés    = NFCI < 0 y diferencial high yield < 5 % y sin subir más de 1 punto en 3 meses
  sin pánico    = VIX < 30 o ≥ 40 % de los valores de la zona sobre su media de 50
  mercado OK    = las tres
Uso: python3 regimen.py → regimen.json"""
import urllib.request, json, os, statistics as st
from rutas import H, DATOS
def fred(s):
    t = urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + s, timeout=40).read().decode().strip().splitlines()[1:]
    L = [(d, float(v)) for d, v in (l.split(",") for l in t) if v not in ("", ".")]
    # v3.2: FRED publica con un día de retraso; REG_EXTRA='{"SP500":["AAAA-MM-DD",valor],...}' añade el cierre más reciente de una fuente pública
    X = json.loads(os.environ.get("REG_EXTRA") or "{}").get(s)
    if X and (not L or X[0] > L[-1][0]): L.append((X[0], float(X[1])))
    return L
def trend(s):
    L = fred(s); last = L[-1][1]; ma = st.mean(v for _, v in L[-200:])
    return dict(fecha=L[-1][0], valor=last, media200=round(ma, 2), dist=round((last / ma - 1) * 100, 1))
G = {}
try:
    vix = fred("VIXCLS"); G["vix"] = dict(fecha=vix[-1][0], valor=vix[-1][1])
    nf = fred("NFCI"); G["nfci"] = dict(fecha=nf[-1][0], valor=nf[-1][1])
    hy = fred("BAMLH0A0HYM2"); G["hy"] = dict(fecha=hy[-1][0], valor=hy[-1][1], hace3m=hy[-64][1] if len(hy) > 64 else None)
    baa = fred("BAA10Y"); G["baa"] = dict(fecha=baa[-1][0], valor=baa[-1][1], hace3m=baa[-64][1] if len(baa) > 64 else None)
except Exception as e: print("aviso FRED", e)
IDX = {}
for z, s in (("EE. UU.", "SP500"), ("Japón", "NIKKEI225")):
    try: IDX[z] = dict(trend(s), nombre={"SP500": "S&P 500", "NIKKEI225": "Nikkei 225"}[s])
    except Exception as e: print("aviso", s, e)
U = {x["sa"]: x for x in json.load(open("universo.json"))}
FI = json.load(open("fichas3.json"))["fichas"]
def zona(x):
    p = x["pais"]
    if p in ("EE. UU.", "España", "Japón"): return p
    if p in ("Taiwán", "Corea", "Hong Kong/China", "China"): return "Asia (Taiwán, Corea, Hong Kong, China)"
    return "Europa"
Z = {}
for sa, f in FI.items():
    if sa not in U or U[sa].get("cartera") or not f.get("sma200") or not f.get("sma50"): continue
    z = Z.setdefault(zona(U[sa]), [0, 0, 0]); z[0] += 1; z[1] += f["px"] >= f["sma200"]; z[2] += f["px"] >= f["sma50"]
# 24/11 (bt/credito.py y bt/regiones.py): el estrés de crédito se mide con lo que SÍ se puede probar desde 1991: NFCI ≥ 0 o el diferencial
# Baa–10 años (BAA10Y) sube más de 0,5 puntos en 3 meses. En 1991-2011 (2001, 2008) esos meses fueron muy malos en EE. UU., Europa, Japón
# y Asia; desde 2012 casi no se ha activado. El high yield (solo 3 años en FRED, sin prueba posible) queda como aviso.
stress, hyAviso = None, None
if G.get("nfci") and G.get("baa"):
    sube = (G["baa"]["valor"] - G["baa"]["hace3m"]) if G["baa"].get("hace3m") is not None else 0
    stress = G["nfci"]["valor"] >= 0 or sube > 0.5
if G.get("hy") and G["hy"].get("hace3m") is not None: hyAviso = G["hy"]["valor"] >= 5 or G["hy"]["valor"] - G["hy"]["hace3m"] > 1
out = {"global": G, "estresCredito": stress, "avisoHighYield": hyAviso, "zonas": {}}
for z, (n, a200, a50) in Z.items():
    b200, b50 = round(a200 / n * 100), round(a50 / n * 100)
    ix = IDX.get(z)
    t_ok = (ix["dist"] >= 0) if ix else b200 >= 50
    p_ok = (G.get("vix", {}).get("valor", 99) < 30) or b50 >= 40
    motivos = []
    motivos.append(("%s %+.1f %% respecto a su media de 200" % (ix["nombre"], ix["dist"])).replace(".", ",") if ix else "%d %% de los valores sobre su media de 200" % b200)
    motivos.append("%d %% de los valores sobre su media de 50" % b50)
    if G.get("vix"): motivos.append(("VIX %.1f" % G["vix"]["valor"]).replace(".", ","))
    if stress is not None: motivos.append(("estrés de crédito: %s (NFCI %.2f; Baa %.2f, %+.2f en 3 meses)" % ("sí" if stress else "no", G["nfci"]["valor"], G["baa"]["valor"], G["baa"]["valor"] - (G["baa"]["hace3m"] or G["baa"]["valor"]))).replace(".", ","))
    if hyAviso: motivos.append(("aviso: el high yield sube %.2f puntos en 3 meses (%.2f %%)" % (G["hy"]["valor"] - G["hy"]["hace3m"], G["hy"]["valor"])).replace(".", ","))
    out["zonas"][z] = dict(n=n, amplitud200=b200, amplitud50=b50, indice=ix, tendencia=t_ok, sinPanico=p_ok, sinEstres=(stress is False), avisoHighYield=bool(hyAviso), ok=bool(t_ok and p_ok and stress is not True), dato="; ".join(motivos))
# v3.2: el estado de cada zona solo cambia si el nuevo valor se repite 3 días seguidos (menos señales falsas al cruzar la media de 200)
import os as _os
_E = json.load(open("regimen_estado.json")) if _os.path.exists("regimen_estado.json") else {}
_HOY = _os.environ.get("REG_FECHA") or __import__("datetime").date.today().isoformat()
for z, v in out["zonas"].items():
    e = _E.get(z); hoy = v["ok"]; v["okHoy"] = hoy
    if e is None: e = dict(ok=hoy, cand=hoy, n=3, fecha=_HOY)
    elif e.get("fecha") != _HOY:
        if hoy == e["ok"]: e.update(cand=hoy, n=0)
        else:
            e["n"] = e["n"] + 1 if e.get("cand") == hoy else 1; e["cand"] = hoy
            if e["n"] >= 3: e["ok"] = hoy
        e["fecha"] = _HOY
    if hoy == e["ok"]: e.update(cand=hoy, n=0)
    v["ok"] = e["ok"]
    if hoy != e["ok"]: v["dato"] += "; cambio a %s pendiente de confirmar (%d de 3 días)" % ("favorable" if hoy else "desfavorable", e["n"])
    _E[z] = e
json.dump(_E, open("regimen_estado.json", "w"), ensure_ascii=False, indent=1)
json.dump(out, open("regimen.json", "w"), ensure_ascii=False, indent=1)
for z, v in out["zonas"].items(): print(z, "OK" if v["ok"] else "NO", "·", v["dato"])
