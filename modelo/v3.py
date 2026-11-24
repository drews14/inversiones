"""Modelo v3 de Oportunidades y Riesgo de caída (20/11/2026).
Cambios sobre v2 (ver claude/mercado-riesgo-caida.md):
- Universo automático (~375 valores, universo.py) en vez de 78 elegidos a mano.
- Factores por PERCENTIL dentro del universo (robusto a escalas y divisas); valor y calidad comparados DENTRO DE SU SECTOR.
- Fuera el retroceso por RSI (comprar caídas salió mal en 2020–26) y fuera el termómetro de la nota (iba igual para todos).
- Momento = cambio a 12 meses + cercanía al máximo de 52 semanas (George y Hwang 2004).
- Calidad = rentabilidad bruta sobre activos (Novy-Marx 2013), ROIC, Piotroski F, deuda/EBITDA; Altman Z bajo = riesgo de quiebra.
- Flujo = posiciones cortas (nivel y cambio en el mes) y recompra/emisión neta de acciones.
- Revisiones (cambio del precio objetivo y de la previsión de BPA a 30 días) en cuanto el archivo diario tenga 30 días.
- Condición «mercado» con datos (regimen.py): tendencia del índice o amplitud, estrés de crédito y VIX.
Escala: Oportunidades 70+ = señal de compra (85+ fuerte), 60–69 esperar, 50–59 vigilar. Riesgo: 70+ = señal de venta/salida.
Uso: python3 v3.py <fecha> → oport_v3.json, caidas_v3.json, v3_raw.json"""
import json, os, sys, gzip, glob, datetime as dt
from rutas import H, DATOS
F = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat(); HOY = dt.date.fromisoformat(F)
CFG = json.load(open("daily_cfg.json")) if os.path.exists("daily_cfg.json") else {}
U = {x["sa"]: x for x in json.load(open("universo.json"))}
FI = json.load(open("fichas3.json"))["fichas"]
RG = json.load(open("regimen.json"))
NEWS_O = CFG.get("news3_o", {})   # noticias que ponen tope a la nota: {símbolo: [nota, texto]} (opcional)
NEWS_R = CFG.get("news3_r", {})
def f1(v, d=1): return ("%.*f" % (d, v)).replace(".", ",")
def zona(x):
    p = x["pais"]
    if p in ("EE. UU.", "España", "Japón"): return p
    if p in ("Taiwán", "Corea", "Hong Kong/China", "China"): return "Asia (Taiwán, Corea, Hong Kong, China)"
    return "Europa"
FIN = ("Financials",)
CICL_S = ("Energy", "Basic Materials", "Materials")
CICL_I = ("Semiconductor", "Auto Manufacturers", "Steel", "Chemicals", "Airlines", "Marine Shipping", "Oil", "Copper", "Aluminum", "Coal", "Paper", "Building Materials")
# --- revisiones: archivo de hace ~30 días (si existe) ---
# 23/11 (aprobado por el dueño): las revisiones de los analistas son la señal gratuita con más respaldo («momentum de beneficios»).
# Ventana ideal ~30 días; mientras el archivo no llega, se usa la de 14-27 días (OLD_DIAS dice cuál).
OLD, OLD_DIAS = None, None
for k in list(range(28, 40)) + list(range(14, 28)):
    p = "archivo/%s.json.gz" % (HOY - dt.timedelta(days=k)).isoformat()
    if os.path.exists(p): OLD = json.load(gzip.open(p, "rt"))["fichas"]; OLD_DIAS = k; break
# serie de precios propia (archivo diario) para el giro del rebote: media de 10 sesiones y mínimo creciente
SERIE = {}
# 23/11: relleno con el histórico diario de StockAnalysis (serie_relleno.py) para no esperar a tener 10 días de archivo propio
if os.path.exists("serie_hist.json"):
    for k, d in json.load(open("serie_hist.json")).items(): SERIE[k] = dict(d)
for p in sorted(glob.glob("archivo/*.json.gz"))[-25:]:
    try:
        for k, v in json.load(gzip.open(p, "rt"))["fichas"].items():
            if v.get("px") and v.get("fecha"): SERIE.setdefault(k, {})[v["fecha"]] = v["px"]
    except Exception: pass
# notas del último día anterior (histéresis: una señal ya dada se mantiene hasta bajar de 60)
PREV = {}
try:
    _D = os.path.join(DATOS, "senales")
    _f = sorted(f for f in os.listdir(_D) if f.endswith(".json") and f[:-5] < F)
    if _f:
        _p = json.load(open(os.path.join(_D, _f[-1])))
        PREV = {r[0]: dict(s=r[1], sr=r[3], rb=(r[6] if len(r) > 6 else None)) for r in _p.get("todas", [])}
except Exception as e: print("sin notas previas:", e)
rows = []
for sa, f in FI.items():
    if sa not in U or f.get("px") is None or not f.get("sma200") or not f.get("sma50"): continue
    x = dict(f); u = U[sa]
    reg = u["region"] if u["region"] in ("EE. UU.", "España") else ("Asia" if u["pais"] in ("Japón", "Taiwán", "Corea", "Hong Kong/China", "China") else "Europa")
    x.update(sa=sa, tk=sa.split("/")[-1], n=u["n"], region=reg, pais=u["pais"], zona=zona(u), bolsa=u["bolsa"])
    x["edad"] = (HOY - dt.date.fromisoformat(f["fecha"])).days if f.get("fecha") else 99
    x["d200"] = (f["px"] / f["sma200"] - 1) * 100; x["d50"] = (f["px"] / f["sma50"] - 1) * 100; x["tr"] = (f["sma50"] / f["sma200"] - 1) * 100
    x["fin"] = (f.get("sector") in FIN)
    x["cicl"] = (f.get("sector") in CICL_S) or any(k in (f.get("industria") or "") for k in CICL_I)
    x["gpa"] = (f["grossMargin"] * f["assetturnover"] / 100) if f.get("grossMargin") is not None and f.get("assetturnover") is not None else None
    x["ey"] = (100 / f["peForward"]) if f.get("peForward") and f["peForward"] > 0 else (f.get("earningsYield"))
    x["ebitdaY"] = (100 / f["evEbitda"]) if f.get("evEbitda") and f["evEbitda"] > 0 else None
    x["prox52"] = (f["px"] / f["h52"]) if f.get("h52") else None
    x["shortChg"] = ((f["shortInterest"] / f["shortPriorMonth"] - 1) * 100) if f.get("shortInterest") and f.get("shortPriorMonth") else None
    x["up"] = f.get("priceTargetChange")
    try: x["dres"] = (dt.datetime.strptime(f.get("earningsdate") or "", "%b %d, %Y").date() - HOY).days
    except Exception: x["dres"] = None
    # recorrido ajustado al riesgo: potencial / amplitud de 52 semanas (ln máx/mín, aproximación de la volatilidad anual)
    x["amp52"] = (__import__("math").log(f["h52"] / f["l52"]) * 100) if f.get("h52") and f.get("l52") and f["l52"] > 0 else None
    x["upAdj"] = (x["up"] / x["amp52"]) if x["up"] is not None and x.get("amp52") else None
    if OLD and sa in OLD:
        o = OLD[sa]
        x["revObj"] = ((f["priceTarget"] / o["priceTarget"] - 1) * 100) if f.get("priceTarget") and o.get("priceTarget") else None
        # previsión de BPA del próximo año = precio / PER estimado (lo que esperan los analistas); revisión = cambio en %
        e1 = f["px"] / f["peForward"] if f.get("px") and f.get("peForward") and f["peForward"] > 0 else None
        e0 = o["px"] / o["peForward"] if o.get("px") and o.get("peForward") and o["peForward"] > 0 else None
        x["revBpa"] = ((e1 / e0 - 1) * 100) if e1 and e0 and abs(e1 / e0 - 1) < 1.5 else None
    rows.append(x)
# --- percentiles ---
def pct(key, group=None, inv=False, filt=lambda x: True):
    G = {}
    for x in rows:
        if x.get(key) is None or not filt(x): continue
        G.setdefault(x[group] if group else "_", []).append(x)
    for g, L in G.items():
        if len(L) < 5 and group:   # grupo pequeño: percentil en todo el universo
            continue
        L.sort(key=lambda x: x[key])
        for i, x in enumerate(L): x["p_" + key + ("_inv" if inv else "")] = (100 - (i + .5) / len(L) * 100) if inv else (i + .5) / len(L) * 100
    if group:   # los que quedaron sin grupo suficiente
        rest = [x for x in rows if x.get(key) is not None and filt(x) and ("p_" + key + ("_inv" if inv else "")) not in x]
        if rest:
            A = sorted([x for x in rows if x.get(key) is not None and filt(x)], key=lambda x: x[key])
            pos = {id(x): (i + .5) / len(A) * 100 for i, x in enumerate(A)}
            for x in rest: x["p_" + key + ("_inv" if inv else "")] = (100 - pos[id(x)]) if inv else pos[id(x)]
for k in ("ch1y", "prox52", "gpa", "roic", "roe", "fScore", "eps3y", "revObj", "revBpa"): pct(k)
pct("debtEbitda", inv=True, filt=lambda x: not x["fin"])
for k in ("ey", "fcfYield", "ebitdaY", "up"): pct(k, group="sector")   # el potencial de analistas, comparado dentro de su sector (Da y Schaumburg 2011)
pct("upAdj")
pct("amp52", inv=True)   # v3.2: seguridad (baja volatilidad) dentro de calidad, como en «Quality minus junk» (Asness, Frazzini y Pedersen)
pct("shortFloat", inv=True); pct("shortChg", inv=True); pct("sharesgrowthyoy", inv=True)
def avg(L):
    L = [(w, v) for w, v in L if v is not None]
    return sum(w * v for w, v in L) / sum(w for w, v in L) if L else None
def lin(x, pts):
    pts = sorted(pts)
    if x <= pts[0][0]: return pts[0][1]
    if x >= pts[-1][0]: return pts[-1][1]
    for (a, b), (c, d) in zip(pts, pts[1:]):
        if a <= x <= c: return b + (d - b) * (x - a) / (c - a)
CONS = {"Strong Buy": 100, "Buy": 80, "Hold": 45, "Sell": 15, "Strong Sell": 5}
for x in rows:
    if x["px"] >= x["sma200"]: rg = "alcista" if x["tr"] >= -3 else "recuperando"
    else: rg = "retroceso" if x["tr"] >= -3 else "bajista"
    x["rg"] = rg
    x["b_tendencia"] = (lin(x["d200"], [(0, 80), (10, 90), (25, 75), (45, 55)]) if rg == "alcista" else 60 if rg == "recuperando"
                        else lin(x["d200"], [(-15, 35), (-8, 55), (0, 70)]) if rg == "retroceso" else lin(x["d200"], [(-40, 5), (-20, 12), (-5, 25)]))
    x["b_momento"] = avg([(1, x.get("p_ch1y")), (1, x.get("p_prox52"))])
    if x["fin"]: x["b_calidad"] = avg([(1, x.get("p_roe")), (1, x.get("p_fScore")), (0.5, x.get("p_amp52_inv"))])
    else: x["b_calidad"] = avg([(1.2, x.get("p_gpa")), (1, x.get("p_roic")), (0.8, x.get("p_fScore")), (0.6, x.get("p_debtEbitda_inv")), (0.6, x.get("p_amp52_inv"))])
    # v3.2: stop según la volatilidad de cada valor ≈ 2 veces su movimiento mensual típico (amplitud de 52 sem. / 2,5 ≈ volatilidad anual; /√12 mensual)
    x["stop"] = int(max(8, min(25, round(0.25 * x["amp52"])))) if x.get("amp52") else 10
    x["b_valor"] = avg([(1.2, x.get("p_ey")), (1, x.get("p_fcfYield")), (0 if x["fin"] else 0.8, x.get("p_ebitdaY"))])
    an = None
    if x.get("cons") and (x.get("analystCount") or 0) >= 3:
        upr = x.get("p_up")
        if upr is not None and (x["up"] or 0) > 60: upr = min(upr, 75)    # objetivos muy por encima tras caídas fuertes: van con retraso
        an = 0.35 * CONS.get(x["cons"], 45) + 0.4 * (upr if upr is not None else 50) + 0.25 * (x.get("p_eps3y") or 50)
        if x.get("p_revObj") is not None or x.get("p_revBpa") is not None:   # con revisiones: pesan la mitad del bloque (la BPA más que el objetivo)
            an = 0.5 * an + 0.5 * avg([(0.8, x.get("p_revObj")), (1.2, x.get("p_revBpa"))])
    x["b_analistas"] = an
    x["b_flujo"] = avg([(1, x.get("p_shortFloat_inv")), (1, x.get("p_shortChg_inv")), (1, x.get("p_sharesgrowthyoy_inv"))])
W = dict(tendencia=20, momento=20, calidad=20, valor=20, analistas=10, flujo=10)
# 23/11 (aprobado por el dueño): pesos por ZONA según los datos públicos de factores (Kenneth French y AQR, bt/factores.py):
# - EE. UU.: el valor ha sido irregular (−1,4 %/año en 2012-19) → menos valor; momentum y calidad se mantienen.
# - Europa y España: momentum (+9-10 %/año en las dos épocas) y calidad AQR funcionan → más momento.
# - Japón: el momentum casi no funciona (+1 %/año); el valor e inversión prudente sí desde 2020 → mucho más valor, menos momento.
# - Asia sin Japón (Taiwán, Corea, Hong Kong, China): momentum (+10-14 %), valor y calidad funcionan en las dos épocas.
WZ = {"EE. UU.": dict(tendencia=20, momento=25, calidad=20, valor=10, analistas=15, flujo=10),
      "Europa": dict(tendencia=20, momento=25, calidad=20, valor=20, analistas=10, flujo=5),
      "Japón": dict(tendencia=20, momento=10, calidad=15, valor=35, analistas=15, flujo=5),
      "Asia": dict(tendencia=15, momento=25, calidad=20, valor=25, analistas=10, flujo=5)}
def pesos_zona(x):
    if x["pais"] == "Japón": return WZ["Japón"]
    if x["region"] == "Asia": return WZ["Asia"]
    if x["region"] in ("Europa", "España"): return WZ["Europa"]
    return WZ.get(x["region"], W)
for x in rows:
    w = dict(pesos_zona(x))
    if OLD is None: w["analistas"] = round(w["analistas"] / 2)   # sin revisiones todavía, los analistas pesan la mitad (su potencial va contra la tendencia)
    if x.get("shortFloat") is None: w["flujo"] = 5   # fuera de EE. UU. no hay datos de cortos: el flujo solo mide recompras
    x["pesos"] = w
    x["atractivo"] = round(avg([(wk, x["b_" + k]) for k, wk in w.items()]) or 0)
    # riesgo de caída: lo contrario, con más peso a tendencia y momento negativos
    x["riesgo_base"] = round(avg([(25, 100 - x["b_tendencia"]), (25, 100 - (x["b_momento"] or 50)), (15, 100 - (x["b_calidad"] or 50)),
                                  (15, 100 - (x["b_valor"] or 50)), (10, 100 - (x["b_analistas"] or 50)), (10, 100 - (x["b_flujo"] or 50))]))
# 23/11 (aprobado por el dueño tras la prueba con el pasado): FUERZA RELATIVA = la empresa está más por encima de su media de 200
# que su índice de la suya (equivale a ir mejor que su mercado en los últimos meses). Índice por país, como en sim_data3.
BENCH_PAIS = {"EE. UU.": "S&P 500", "España": "IBEX 35", "Japón": "Nikkei 225", "Taiwán": "Taiex", "Corea": "Kospi", "Hong Kong/China": "Hang Seng", "China": "CSI 300",
              "Reino Unido": "FTSE 100", "Suiza": "SMI", "Alemania": "DAX", "Francia": "CAC 40", "Italia": "FTSE MIB"}
BD200 = json.load(open("bench.json")).get("d200", {}) if os.path.exists("bench.json") else {}
for _z, _ix in (("EE. UU.", "S&P 500"), ("Japón", "Nikkei 225")):     # respaldo con FRED (regimen.json) si falta la serie del ETF
    if _ix not in BD200 and (RG["zonas"].get(_z) or {}).get("indice"): BD200[_ix] = RG["zonas"][_z]["indice"]["dist"]
def fuerza(x):
    ix = BENCH_PAIS.get(x["pais"], "Stoxx 600"); b = BD200.get(ix)
    if b is None: return dict(k="fuerza", ok=True, d="sin dato de %s: no se aplica" % ix)
    return dict(k="fuerza", ok=x["d200"] > b, d="%+.0f %% sobre su media de 200, frente a %+.0f %% del %s" % (x["d200"], b, ix))
CORTO = {"fuerza": "va mejor que su índice", "resultados": "sin resultados en 7 días", "tendencia": "tendencia de fondo", "giro": "giro a corto (precio sobre la media de 50)", "mercado": "mercado favorable", "nota": "atractivo de 70 o más",
         "valoracion": "valoración fiable", "datos": "datos recientes", "noticias": "sin noticias negativas"}
TOPE = {"fuerza": 64, "resultados": 64, "tendencia": 49, "valoracion": 59, "giro": 64, "datos": 64, "noticias": 64, "mercado": 69, "nota": 69}
def opp(x):
    z = RG["zonas"].get(x["zona"], {})
    fallos = []
    if (x.get("roic") is not None and x["roic"] < 5) and (x.get("roe") or 0) < 5: fallos.append("rentabilidad muy baja (ROIC y ROE < 5 %)")
    if not x["fin"] and (x.get("debtEquity") or 0) >= 3: fallos.append("deuda elevada")
    if x["edad"] > 21: fallos.append("datos con más de 21 días (cotización congelada o suspendida)")
    pico = x["cicl"] and x.get("peForward") is not None and 0 < x["peForward"] < 8
    quiebra = (not x["fin"]) and x.get("zScore") is not None and x["zScore"] < 1.8
    nw = NEWS_O.get(x["sa"]) or NEWS_O.get(x["tk"])
    cond = [
        dict(k="tendencia", ok=(x["px"] >= x["sma200"] and x["tr"] >= -3) or (x["rg"] == "retroceso" and x["d200"] >= -8) or x["rg"] == "recuperando" and x["d50"] >= 0,
             d="%s %% vs. media de 200" % ("%+.0f" % x["d200"]).replace(".", ",")),
        dict(k="giro", ok=x["d50"] >= 0, d="%s %% vs. media de 50" % ("%+.0f" % x["d50"]).replace(".", ",")),
        dict(k="mercado", ok=bool(z.get("ok")), d=x["zona"] + ": " + z.get("dato", "sin datos")),
        fuerza(x),
        dict(k="nota", ok=x["atractivo"] >= 70 and not fallos, d="%d%s" % (x["atractivo"], " · " + ", ".join(fallos) if fallos else "")),
        dict(k="valoracion", ok=not (pico or quiebra), d=("PER est. %s en sector cíclico" % f1(x["peForward"])) if pico else ("Altman Z %s: riesgo financiero" % f1(x["zScore"])) if quiebra else
             ("PER est. %s" % f1(x["peForward"]) if x.get("peForward") else "PER n/d")),
        dict(k="datos", ok=x["edad"] <= 5, d="ficha de hace %d días" % x["edad"]),
    ]
    if nw: cond.append(dict(k="noticias", ok=nw[0] >= 45, d=nw[1]))
    if x.get("dres") is not None and 0 <= x["dres"] <= 7:
        cond.append(dict(k="resultados", ok=False, d="presenta resultados en %d días (%s)" % (x["dres"], x.get("earningsdate"))))
    tot = x["atractivo"]
    for c in cond:
        if not c["ok"]: tot = min(tot, TOPE[c["k"]])
    est = "Descartada" if fallos else "Señal de compra" if tot >= 70 else "Esperar" if tot >= 60 else "Vigilar" if tot >= 50 else "Sin señal"
    x["mantiene"] = False
    pv = PREV.get(x["sa"], {})
    if not fallos and est == "Esperar" and (pv.get("s") or 0) >= 70 and next(c["ok"] for c in cond if c["k"] == "tendencia"):
        est, x["mantiene"] = "Señal de compra", True     # ya tenía señal: se mantiene mientras no baje de 60 ni se rompa la tendencia
    # --- segunda señal: REBOTE CONFIRMADO (empresa buena que ha caído fuerte y empieza a girarse) ---
    reb = None
    caida = (1 - x["px"] / x["h52"]) * 100 if x.get("h52") else 0
    cal, val = x["b_calidad"] or 0, x["b_valor"] or 0
    if caida >= 25 and not fallos:
        S = [p for _, p in sorted(SERIE.get(x["sa"], {}).items())]
        if len(S) >= 10:
            m10 = sum(S[-10:]) / 10; minimo_creciente = min(S[-3:]) > min(S[-10:-3])
            giro_ok = (x["px"] > m10 and minimo_creciente) or x["d50"] >= 0
            giro_d = "precio %s la media de 10 sesiones; mínimo %s" % ("sobre" if x["px"] > m10 else "bajo", "más alto" if minimo_creciente else "sin subir")
        else:   # hasta tener 10 días de archivo: aproximación con lo que da la ficha
            rebote = (x["px"] / x["l52"] - 1) * 100 if x.get("l52") else 0
            giro_ok = x["d50"] >= 0 or ((x.get("rsi") or 0) >= 50 and rebote >= 10 and x["d50"] >= -5)
            giro_d = "%s %% sobre su mínimo de 52 sem.; RSI %s; %s %% vs. media de 50" % (f1(rebote, 0), f1(x.get("rsi") or 0, 0), ("%+.0f" % x["d50"]))
        rc = [dict(k="calidadvalor", ok=cal >= 55 and val >= 55 and (cal + val) / 2 >= 70, d="calidad %d, valor %d" % (cal, val)),
              dict(k="caida", ok=True, d="−%s %% desde su máximo de 52 sem." % f1(caida, 0)),
              dict(k="girorebote", ok=giro_ok, d=giro_d),
              # 23/11 (aprobado por el dueño): el rebote se compra cuando SU MERCADO YA HA VUELTO a la tendencia alcista, no mientras cae
              # (en el histórico, comprar con el mercado cayendo falló en 2012-2019 y en 2020-2026)
              dict(k="mercadoalza", ok=bool(z.get("tendencia")),
                   d=x["zona"] + ": " + ("%d %% de los valores sobre su media de 200" % z.get("amplitud200", 0)) + ((", %s %+.1f %% vs. su media de 200" % (z["indice"]["nombre"], z["indice"]["dist"])).replace(".", ",") if z.get("indice") else "")),
              dict(k="panico", ok=bool(z.get("sinPanico")) and bool(z.get("sinEstres")), d=x["zona"] + ": " + ("sin pánico ni estrés de crédito" if z.get("sinPanico") and z.get("sinEstres") else "pánico o estrés de crédito")),
              dict(k="valoracion", ok=not (pico or quiebra), d=next(c["d"] for c in cond if c["k"] == "valoracion")),
              dict(k="datos", ok=x["edad"] <= 5, d="ficha de hace %d días" % x["edad"])]
        if nw: rc.append(dict(k="noticias", ok=nw[0] >= 45, d=nw[1]))
        if x.get("dres") is not None and 0 <= x["dres"] <= 7: rc.append(dict(k="resultados", ok=False, d="presenta resultados en %d días" % x["dres"]))
        nr = round(0.4 * cal + 0.4 * val + 0.2 * (x["b_analistas"] or 50))
        for c in rc:
            if not c["ok"]: nr = min(nr, 64 if c["k"] != "calidadvalor" else 49)
        if nr < 70 and all(c["ok"] for c in rc): rc.append(dict(k="notarebote", ok=False, d="nota de rebote %d (hace falta 70)" % nr))
        if rc[0]["ok"]:
            reb = dict(nota=nr, estado="Rebote confirmado" if nr >= 70 else "Vigilar rebote", cumple=sum(c["ok"] for c in rc), total=len(rc),
                       condiciones=[dict(clave=c["k"], ok=c["ok"], dato=c["d"]) for c in rc], salida="Salir si marca un nuevo mínimo de 52 semanas o pierde un %d %% desde la compra" % x["stop"], tamano="mitad del importe sugerido (señal experimental)")
            if reb["estado"] == "Rebote confirmado" and est != "Señal de compra": est, tot = "Rebote confirmado", max(tot, nr)
    x["_reb"] = reb
    return tot, est, cond, fallos
def risk(x):
    z = RG["zonas"].get(x["zona"], {})
    cond = [
        dict(k="tendencia", ok=x["rg"] == "bajista" or x["d200"] < -8, d="%s %% vs. media de 200" % ("%+.0f" % x["d200"]).replace(".", ",")),
        dict(k="giro", ok=x["d50"] < 0, d="%s %% vs. media de 50" % ("%+.0f" % x["d50"]).replace(".", ",")),
    ]
    tot = x["riesgo_base"]
    x["mantieneR"] = False
    if not cond[0]["ok"]: tot = min(tot, 59)       # sin tendencia bajista no hay señal de venta
    if not cond[1]["ok"]: tot = min(tot, 64)       # si ya recupera la media de 50, no
    if not (z.get("ok")): tot = min(100, tot + 5)  # mercado desfavorable suma riesgo
    if x["edad"] > 5: tot = min(tot, 64)            # 24/11: con datos de más de 5 días no hay señal de venta (cotización retrasada o congelada)
    est = "Riesgo alto" if tot >= 70 else "Riesgo" if tot >= 60 else "Vigilar" if tot >= 50 else "Sin señal"
    if est == "Riesgo" and (PREV.get(x["sa"], {}).get("sr") or 0) >= 70 and cond[0]["ok"]: est, x["mantieneR"] = "Riesgo alto", True
    return tot, est, cond
SECT = {"Healthcare": "Salud", "Consumer Staples": "Consumo básico", "Consumer Discretionary": "Consumo discrecional", "Financials": "Finanzas", "Technology": "Tecnología",
        "Industrials": "Industria", "Communication Services": "Comunicaciones", "Energy": "Energía", "Basic Materials": "Materiales", "Materials": "Materiales",
        "Utilities": "Eléctricas y servicios", "Real Estate": "Inmobiliario"}
REG_T = {"alcista": "Tendencia alcista", "retroceso": "Retroceso dentro de tendencia alcista", "recuperando": "Intentando recuperar tendencia", "bajista": "Tendencia bajista"}
CES = {"Strong Buy": "Compra fuerte", "Buy": "Comprar", "Hold": "Mantener", "Sell": "Vender", "Strong Sell": "Venta fuerte"}
def bloques(x, inv):
    B = {k: (None if x["b_" + k] is None else round(100 - x["b_" + k] if inv else x["b_" + k])) for k in W}
    return B
def tags(x, inv):
    t = [REG_T[x["rg"]], "%+.0f %% vs. media 200" % x["d200"], "%+.0f %% vs. media 50" % x["d50"], "%+.0f %% en 1 año" % (x.get("ch1y") or 0),
         ("a %.0f %% del máximo de 52 sem." % ((1 - x["prox52"]) * 100)) if x.get("prox52") else None,
         "PER est. " + f1(x["peForward"]) if x.get("peForward") else "PER n/d", "ROIC " + f1(x["roic"], 0) + " %" if x.get("roic") is not None else None,
         "Rent. bruta/activos " + f1(x["gpa"] * 100, 0) + " %" if x.get("gpa") is not None and not x["fin"] else None, "Piotroski " + str(int(x["fScore"])) if x.get("fScore") is not None else None,
         "Altman Z " + f1(x["zScore"]) if x.get("zScore") is not None and not x["fin"] else None, "Cortos " + f1(x["shortFloat"]) + " %" if x.get("shortFloat") is not None else None,
         (CES.get(x["cons"], x["cons"]) + " (" + str(int(x.get("analystCount") or 0)) + ")") if x.get("cons") else None, "Sector: " + SECT.get(x.get("sector"), x.get("sector") or "n/d")]
    return [s.replace(".", ",") if s and s.startswith("+") is False and False else s for s in t if s]
def motivo(x, inv):
    p = []
    if not inv:
        if x["b_tendencia"] >= 70: p.append("tendencia de fondo alcista")
        if (x["b_momento"] or 0) >= 70: p.append("momento entre el 30 % mejor del universo")
        if (x["b_calidad"] or 0) >= 70: p.append("calidad alta (rentabilidad y solidez)")
        if (x["b_valor"] or 0) >= 70: p.append("barata frente a su sector")
        if (x["b_analistas"] or 0) >= 75: p.append("analistas favorables")
        if (x["b_flujo"] or 0) >= 70: p.append("pocos cortos y recompras")
        return ("A favor: " + "; ".join(p) + ".") if p else "Sin puntos fuertes destacados."
    if x["rg"] == "bajista": p.append("tendencia bajista (%s %% bajo su media de 200)" % f1(-x["d200"], 0))
    if (x["b_momento"] or 50) <= 30: p.append("momento entre el 30 % peor del universo")
    if (x["b_calidad"] or 50) <= 30: p.append("calidad baja")
    if (x["b_valor"] or 50) <= 30: p.append("cara frente a su sector")
    if (x["b_flujo"] or 50) <= 30: p.append("muchos cortos o emisión de acciones")
    if (x.get("zScore") is not None and x["zScore"] < 1.8 and not x["fin"]): p.append("Altman Z bajo (riesgo financiero)")
    nw = NEWS_R.get(x["sa"]) or NEWS_R.get(x["tk"])
    if nw: p.append(nw[1])
    return ("Por qué puede caer: " + "; ".join(p) + ".") if p else "Sin señales de riesgo destacadas."
def item(x, inv):
    if inv: tot, est, cond = risk(x); fallos = []
    else: tot, est, cond, fallos = opp(x)
    falta = []
    if not inv and (x["up"] or 0) > 60: falta.append("El objetivo de los analistas está un %s %% por encima: tras caídas fuertes suelen ir con retraso; se ha limitado su peso" % f1(x["up"], 0))
    return dict(revisiones=None if x.get("revObj") is None and x.get("revBpa") is None else dict(objetivo=None if x.get("revObj") is None else round(x["revObj"], 1), bpa=None if x.get("revBpa") is None else round(x["revBpa"], 1), dias=OLD_DIAS),
                region=x["region"], nombre=x["n"], ticker=x["tk"], sa=x["sa"], mercado=x["bolsa"], pais=x["pais"], sector=x.get("sector"), industria=x.get("industria"),
                divisa=x.get("divisa"), precio=x["px"], var=None, fechaDatos=x["fecha"], objetivo=x.get("priceTarget"), potencial=None if x["up"] is None else round(x["up"], 2),
                consenso=CES.get(x.get("cons"), x.get("cons")), nAnalistas=int(x.get("analystCount") or 0), tags=tags(x, inv), puntuacion=int(tot),
                atractivo=(x["riesgo_base"] if inv else x["atractivo"]), senales=bloques(x, inv), estado=est, falta=falta, descarte=fallos, regimen=REG_T[x["rg"]],
                motivo=motivo(x, inv), confianza=("Alta" if x["edad"] <= 7 else "Media" if x["edad"] <= 21 else "Baja"),
                recorrido=dict(potencial=None if x["up"] is None else round(x["up"], 1), sector=None if x.get("p_up") is None else round(x["p_up"]),
                               amp52=None if x.get("amp52") is None else round(x["amp52"]), ajustado=None if x.get("upAdj") is None else round(x["upAdj"], 2),
                               pct=None if x.get("p_upAdj") is None else round(x["p_upAdj"]),
                               nivel=None if x.get("p_upAdj") is None else ("alto" if x["p_upAdj"] >= 67 else "medio" if x["p_upAdj"] >= 33 else "bajo")),
                rebote=(x.get("_reb") if not inv else None), mantiene=(x.get("mantieneR") if inv else x.get("mantiene")), pesos=x.get("pesos"),
                d200=round(x["d200"], 1), rg=x["rg"], amp52=None if x.get("amp52") is None else round(x["amp52"]), stop=x["stop"], resultadosEn=x.get("dres"),
                entrada=dict(cumple=sum(c["ok"] for c in cond), total=len(cond), condiciones=[dict(clave=c["k"], ok=c["ok"], dato=c["d"]) for c in cond]))
O = [item(x, False) for x in rows]; R = [item(x, True) for x in rows]
RANK = {"Rebote confirmado": 0, "Señal de compra": 0, "Riesgo alto": 0, "Esperar": 1, "Riesgo": 1, "Vigilar": 2, "Sin señal": 3, "Descartada": 4}
lim = {"EE. UU.": 20, "Europa": 20, "España": 20, "Asia": 20}
def doc(out, risky):
    out = [x for x in out if not U.get(x["sa"], {}).get("cartera")]   # 23/11: las de la cartera real solo se vigilan
    items, extras, desc, conc = [], [], [], []
    for reg, n in lim.items():
        L = sorted([x for x in out if x["region"] == reg], key=lambda x: (RANK.get(x["estado"], 9), -x["puntuacion"], -x["atractivo"]))   # v3.2: el recorrido (precio objetivo) ya no ordena: predice poco
        ok = [x for x in L if x["estado"] != "Descartada"]
        # 23/11 (pedido del dueño): sin cupo de 20 por zona. Se muestran TODAS las que están en zona de compra
        # (Señal de compra, Rebote confirmado) o de salida (Riesgo alto); las cercanas, aparte y plegadas.
        ACT = ("Riesgo alto",) if risky else ("Señal de compra", "Rebote confirmado")
        sel = [x for x in ok if x["estado"] in ACT]; items += sel
        # aviso de concentración: más de 3 del mismo sector entre las señales (o los riesgos) de la lista
        act = sel
        cs = {}
        for x in act: cs[x.get("sector") or "?"] = cs.get(x.get("sector") or "?", 0) + 1
        for k, c in cs.items():
            if c > 3: conc.append(dict(region=reg, sector=k, n=c, total=len(act)))
        extras += [x for x in ok if x["estado"] == ("Riesgo" if risky else "Esperar")]
        if not risky:
            for x in L:
                if x["estado"] in ("Vigilar", "Sin señal", "Descartada") and x["atractivo"] >= 70 and x not in items:
                    m = [CORTO[c["clave"]] + " (" + c["dato"] + ")" for c in x["entrada"]["condiciones"] if not c["ok"] and c["clave"] in ("tendencia", "valoracion")]
                    desc.append(dict(nombre=x["nombre"], ticker=x["ticker"], region=reg, puntuacion=x["puntuacion"],
                                     motivo="; ".join(x["descarte"]) if x["descarte"] else ("sin señal: falla " + " y ".join(m) if m else "sin señal")))
    cnt = {}
    for x in items: cnt[x["estado"]] = cnt.get(x["estado"], 0) + 1
    falt = {}
    for x in items:
        for c in x["entrada"]["condiciones"]:
            if not c["ok"]: falt[CORTO[c["clave"]]] = falt.get(CORTO[c["clave"]], 0) + 1
    top = sorted(falt.items(), key=lambda kv: -kv[1])[:3]
    nU = {r: sum(1 for x in out if x["region"] == r) for r in lim}
    if not risky:
        nreb = sum(1 for x in out if (x.get("rebote") or {}).get("estado") == "Rebote confirmado")
        nota = ("Cómo leer la nota: 70 o más = señal de compra del modelo (85 o más, fuerte); 60–69 = esperar; 50–59 = vigilar; menos de 50 = sin señal. "
                "Hay dos tipos de compra: «Señal de compra» (tendencia ya sana) y «Rebote confirmado» (empresa de calidad y barata que ha caído un 25 % o más y empieza a girarse; entra antes, con más riesgo y salida más corta). "
                + ("Rebotes confirmados hoy en todo el universo: %d. " % nreb)
                + "Solo llega a 70 si se cumplen todas las condiciones de entrada; cada una que falla pone un tope. "
                + ("Hoy hay %d con señal de compra" % cnt.get("Señal de compra", 0) if cnt.get("Señal de compra") else "Hoy ninguna llega a 70: no hay señal de compra")
                + ("; %d en «Esperar»" % cnt["Esperar"] if cnt.get("Esperar") else "") + ". "
                + ("Lo que más falta: %s." % "; ".join("%s (%d)" % kv for kv in top) if top else ""))
    else:
        nota = ("Cómo leer la nota de riesgo: 70 o más = señal de venta o salida del modelo (exige tendencia bajista y que siga cayendo); 60–69 = riesgo; 50–59 = vigilar. "
                "Hoy hay %d con señal de venta, %d en riesgo y %d para vigilar." % (cnt.get("Riesgo alto", 0), cnt.get("Riesgo", 0), cnt.get("Vigilar", 0)))
    items.sort(key=lambda x: (RANK.get(x["estado"], 9), -x["puntuacion"], -x["atractivo"]))
    extras.sort(key=lambda x: -x["puntuacion"])
    lim2 = {r: sum(1 for x in items if x["region"] == r) for r in lim}
    fechas = sorted({x["fechaDatos"] for x in items} or {x["fechaDatos"] for x in out})
    return {"fecha": F, "actualizado": F + "T08:00:00+01:00", "ejemplo": False, "version": "v3.2", "porRegion": False, "limites": lim2, "nota": nota,
            "regimen": {z: dict(ok=v["ok"], dato=v["dato"]) for z, v in RG["zonas"].items()},
            "universo": "%d valores analizados con una regla fija: S&P 500 y Nasdaq 100 completos en EE. UU. y, en el resto, las mayores de cada bolsa (≈ IBEX 35, Euro Stoxx 50 y resto de Europa, Nikkei 225, CSI 300, Taiwán 150, KOSPI 200 y Hong Kong): %d de EE. UU., %d de Europa, %d de España y %d de Asia. Se muestran todas las que están en zona de %s, juntas y ordenadas por nota." % (len(out), nU["EE. UU."], nU["Europa"], nU["España"], nU["Asia"], "salida" if risky else "compra"),
            "fuenteDatos": "Fichas de StockAnalysis.com (último cierre: %s); régimen de mercado con FRED (S&P 500, Nikkei 225, VIX, NFCI, high yield) y amplitud del universo. Valor y calidad se comparan dentro de cada sector." % ", ".join(dt.date.fromisoformat(f).strftime("%d/%m") for f in fechas),
            "concentracion": conc, "bloques": list(W.keys()), "items": [{k: v for k, v in x.items() if k != "descarte"} for x in items],
            "extras": [dict(nombre=x["nombre"], ticker=x["ticker"], region=x["region"], puntuacion=x["puntuacion"], estado=x["estado"]) for x in extras], "descartadas": desc,
            "rebotes": [] if risky else [dict(nombre=x["nombre"], ticker=x["ticker"], sa=x["sa"], region=x["region"], nota=x["rebote"]["nota"], estado=x["rebote"]["estado"],
                         caida=next(c["dato"] for c in x["rebote"]["condiciones"] if c["clave"] == "caida"),
                         falta=[c["clave"] for c in x["rebote"]["condiciones"] if not c["ok"]])
                        for x in sorted([x for x in out if x.get("rebote")], key=lambda x: (x["rebote"]["estado"] != "Rebote confirmado", -x["rebote"]["nota"]))][:20]}
json.dump(doc(O, False), open("oport_v3.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(doc(R, True), open("caidas_v3.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump({"O": O, "R": R}, open("v3_raw.json", "w"), ensure_ascii=False, separators=(",", ":"))
import shutil   # lo que lee la app
shutil.copy("oport_v3.json", os.path.join(DATOS, "oportunidades.json")); shutil.copy("caidas_v3.json", os.path.join(DATOS, "caidas.json"))
from collections import Counter
print("oport", Counter(x["estado"] for x in O)); print("riesgo", Counter(x["estado"] for x in R))
for reg in lim:
    print(reg, [(x["ticker"], x["puntuacion"], x["atractivo"]) for x in sorted([x for x in O if x["region"] == reg], key=lambda x: -x["puntuacion"])[:8]])
