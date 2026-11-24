"""Datos diarios del simulador con el modelo v3 (08:00, después de v3.py):
 - simprecios.json: precio del último cierre de los ~375 valores del universo (clave = símbolo de StockAnalysis: "AAPL", "bme/ITX", "tyo/7203"),
   estado del modelo (oportunidad y riesgo), índice de referencia, cambios del BCE e índices; "alias" para los tickers antiguos (SAN → bme/SAN).
 - senales_<fecha>.json: señales del día (Señal de compra y Esperar; Riesgo y Riesgo alto).
Uso: SIM_TS=<iso opcional> python3 sim_data3.py <fecha>"""
import json, sys, os, csv, io, urllib.request, datetime as dt
from rutas import H, DATOS
F = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
FI3 = json.load(open("fichas3.json"))["fichas"] if os.path.exists("fichas3.json") else {}   # 23/11: apertura del día (pxo) para ejecutar a la apertura
V = json.load(open("v3_raw.json")); U = {x["sa"]: x for x in json.load(open("universo.json"))}
IX = json.load(open("indices_%s.json" % F)) if os.path.exists("indices_%s.json" % F) else None   # niveles de los índices (fase 4)
CUR = "USD+GBP+JPY+KRW+HKD+CHF+DKK+SEK+NOK+AUD+CAD+INR+SGD+BRL+MXN+CNY"
t = urllib.request.urlopen("https://data-api.ecb.europa.eu/service/data/EXR/D.%s.EUR.SP00.A?lastNObservations=1&format=csvdata" % CUR, timeout=30).read().decode()
fx = {"€": 1, "EUR": 1}
for r in csv.DictReader(io.StringIO(t)): fx[r["CURRENCY"]] = float(r["OBS_VALUE"])
fx["$"] = fx["USD"]; fx["GBX"] = round(fx["GBP"] * 100, 4); fx["GBp"] = fx["GBX"]
fxnota = "Cambios de referencia del BCE. GBX = peniques (GBP × 100)."
try:
    L = [l.split(",") for l in urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXTAUS", timeout=30).read().decode().strip().splitlines()[1:]]
    d, v = [x for x in L if x[1].strip() not in ("", ".")][-1]
    fx["TWD"] = round(float(v) * fx["USD"], 4); fxnota += " TWD = cruce de la serie DEXTAUS de la Fed (%s) con el USD del BCE." % d
except Exception as e: print("sin TWD:", e)
BENCH = {"EE. UU.": "S&P 500", "España": "IBEX 35", "Japón": "Nikkei 225", "Taiwán": "Taiex", "Corea": "Kospi", "Hong Kong/China": "Hang Seng", "China": "CSI 300", "Reino Unido": "FTSE 100",
         "Suiza": "SMI", "Alemania": "DAX", "Francia": "CAC 40", "Italia": "FTSE MIB"}
eo = {x["sa"]: x for x in V["O"]}; er = {x["sa"]: x for x in V["R"]}
val = {}
for sa, o in eo.items():
    r = er.get(sa, {}); u = U.get(sa, {})
    val[sa] = dict(n=o["nombre"], r=o["region"], d=o["divisa"], p=o["precio"], o=(FI3.get(sa) or {}).get("pxo"), f=o["fechaDatos"], m=o["mercado"], sa=sa, b=BENCH.get(u.get("pais"), "Stoxx 600"),
                   eo=o["estado"], po=o["puntuacion"], pa=o["atractivo"], v=o.get("amp52"), st=o.get("stop"), s=o.get("sector"), d2=o.get("d200"), rgo=o.get("rg"), ec=o["entrada"]["cumple"], et=o["entrada"]["total"],
                   ef=[c["clave"] for c in o["entrada"]["condiciones"] if not c["ok"]], rb=(o.get("rebote") or {}).get("estado"), er=r.get("estado"), pr=r.get("puntuacion"), reg=o["regimen"])
# alias de los tickers del modelo anterior (señales del 20/11 08:00)
EXV2 = {"Shanghái": "sha/", "Shenzhen": "she/", "Taiwán": "tpe/", "Tokio": "tyo/", "Corea": "krx/", "Hong Kong": "hkg/", "Londres": "lon/", "Suiza": "swx/", "Euronext Ámsterdam": "ams/", "Xetra": "etr/",
        "Euronext París": "epa/", "Copenhague": "cph/", "Borsa Italiana": "bit/", "BME": "bme/"}
alias = {}
try:
    from data import RAW
    for reg, Lr in RAW.items():
        for x in Lr:
            k = EXV2.get(x[2], "") + x[1].replace(" ", ".")
            if k != x[1]: alias[x[1]] = k
except Exception as e: print("sin alias:", e)
idx = {}
if IX:
    m = {it["nombre"]: it["valor"] for g in IX["grupos"] for it in g["items"] if it.get("valor") is not None}
    idx = {k: v for k, v in m.items() if k in set(BENCH.values()) | {"Euro Stoxx 50", "Stoxx 600"}}
    idx.update({"EE. UU.": m.get("S&P 500"), "Europa": m.get("Euro Stoxx 50"), "España": m.get("IBEX 35")})
BN = {}
if os.path.exists("bench.json"):
    _b = json.load(open("bench.json"))
    if _b.get("fecha") == F:
        BN = dict(_b["precios"]); BN.update({r: BN.get(i) for r, i in (("EE. UU.", "S&P 500"), ("Europa", "Euro Stoxx 50"), ("España", "IBEX 35")) if BN.get(i)})
sp = {"fecha": F, "actualizado": os.environ.get("SIM_TS", F + "T08:00:00+01:00"), "version": "v3", "fx": fx, "fxNota": fxnota, "indices": idx, "bench": BN, "alias": alias, "valores": val}
json.dump(sp, open("simprecios.json", "w"), ensure_ascii=False, separators=(",", ":"))
pick = lambda D, ok: [dict(t=x["sa"], n=x["nombre"], r=x["region"], b=val[x["sa"]]["b"], e=x["estado"], s=x["puntuacion"], a=x["atractivo"], p=x["precio"], d=x["divisa"], f=x["fechaDatos"])
                      for x in D if x["estado"] in ok and not U.get(x["sa"], {}).get("cartera")]   # 23/11: las de la cartera real no dan señales
sg = {"fecha": F, "version": "v3", "indices": idx, "bench": BN, "op": pick(V["O"], ("Señal de compra", "Rebote confirmado", "Esperar")), "ri": pick(V["R"], ("Riesgo alto", "Riesgo")),
      # todas las notas del día (para calibrar con datos qué tramo de nota bate a su índice): [símbolo, nota oportunidad, atractivo, nota riesgo, precio, índice de referencia]
      # 23/11: + bq = bloques de la nota [tendencia, momento, calidad, valor, analistas, flujo] y cf = condiciones de compra que fallan,
      # para medir con datos reales qué parte del modelo predice y cuál sobra (Seguimiento → «¿Qué parte de la nota acierta?»)
      "modelo": "v3.3", "universo": len(U), "campos": ["t", "s", "a", "sr", "p", "b", "rb", "bq", "cf", "rv"],
      "todas": [[sa, v["po"], v["pa"], v["pr"], v["p"], v["b"], (eo[sa].get("rebote") or {}).get("nota"),
                 [(eo[sa].get("senales") or {}).get(k) for k in ("tendencia", "momento", "calidad", "valor", "analistas", "flujo")],
                 [c["clave"] for c in (eo[sa].get("entrada") or {}).get("condiciones", []) if not c["ok"]],
                 [((eo[sa].get("revisiones") or {}).get("objetivo")), ((eo[sa].get("revisiones") or {}).get("bpa"))]] for sa, v in val.items()]}
json.dump(sg, open("senales_%s.json" % F, "w"), ensure_ascii=False, separators=(",", ":"))
# archivos del artefacto: datos/senales/<fecha>.json + índice datos/senales.json
D = DATOS; os.makedirs(os.path.join(D, "senales"), exist_ok=True)
json.dump(sg, open(os.path.join(D, "senales", F + ".json"), "w"), ensure_ascii=False, separators=(",", ":"))
fechas = sorted(f[:-5] for f in os.listdir(os.path.join(D, "senales")) if f.endswith(".json"))
json.dump({"fechas": fechas}, open(os.path.join(D, "senales.json"), "w"))
print("simprecios:", len(val), "valores, alias", len(alias), "; señales:", len(sg["op"]), "oportunidades,", len(sg["ri"]), "riesgos")
