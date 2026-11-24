"""Relleno de precios diarios (23/11/2026, pedido del dueño): el «giro» del rebote necesita 10 sesiones de precios diarios y el
archivo propio solo empezó el 20/11. Se rellenan los últimos ~40 cierres desde la página de histórico de StockAnalysis
(/history/, misma fuente y mismo User-Agent, ~1 consulta por segundo) para los valores que pueden ser rebote
(≥ 20 % bajo su máximo de 52 semanas) y los de la cartera real. Salida: serie_hist.json {símbolo: {fecha: cierre}} que v3.py
une con el archivo diario. Uso: python3 serie_relleno.py [todos]"""
import urllib.request, re, json, os, sys, time
from rutas import H, DATOS
UA = {"User-Agent": "cartera-inversiomes/1.0"}
FI = json.load(open("fichas3.json"))["fichas"]; U = {x["sa"]: x for x in json.load(open("universo.json"))}
todos = len(sys.argv) > 1 and sys.argv[1] == "todos"
L = [sa for sa, f in FI.items() if sa in U and f.get("px") and f.get("h52") and (todos or f["px"] <= 0.80 * f["h52"] or U[sa].get("cartera"))]
out = json.load(open("serie_hist.json")) if os.path.exists("serie_hist.json") else {}
base = lambda sa: "https://stockanalysis.com/" + ("quote/%s/" % sa if "/" in sa else "stocks/%s/" % sa.lower())
ok = fal = 0
for i, sa in enumerate(L):
    try:
        s = urllib.request.urlopen(urllib.request.Request(base(sa) + "history/", headers=UA), timeout=40).read().decode()
        S = {}
        for o in re.findall(r'\{[^{}]*?t:"\d{4}-\d{2}-\d{2}"[^{}]*\}', s):
            t = re.search(r't:"(\d{4}-\d{2}-\d{2})"', o).group(1); c = re.search(r'(?<![a-z])c:([-\d.]+)', o)
            if c: S[t] = float(c.group(1))
        if len(S) >= 10: out[sa] = dict(sorted(S.items())[-45:]); ok += 1
        else: fal += 1
    except Exception: fal += 1
    if i % 100 == 0: print(i, "…", flush=True); json.dump(out, open("serie_hist.json", "w"))
    time.sleep(1.0)
json.dump(out, open("serie_hist.json", "w"))
print("serie_hist: %d valores con precios diarios, %d fallos (de %d)" % (ok, fal, len(L)))
