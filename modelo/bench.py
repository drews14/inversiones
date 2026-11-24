"""Índices de referencia automáticos (v3.2, desde el 23/11/2026).
Para MEDIR el modelo se usa el precio de un ETF que replica cada índice, sacado de StockAnalysis (misma fuente que las acciones):
siempre el mismo instrumento, en la moneda local del índice, sin huecos ni búsquedas manuales.
Los niveles de los índices que se muestran en pantalla siguen saliendo de mercado/indices.
Salida: bench.json {fecha, etf:{índice: símbolo}, precios:{índice: precio}, fechas:{índice: fecha del cierre}, var:{índice: % día}}
y bench_hist.json (un registro por fecha). Uso: python3 bench.py <fecha>"""
import urllib.request, re, json, os, sys, time, datetime as dt
from rutas import H, DATOS
F = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
UA = {"User-Agent": "cartera-inversiomes/1.0"}
ETF = {"S&P 500": "etf/spy", "IBEX 35": "quote/bme/BBVAI", "Euro Stoxx 50": "quote/etr/EXW1", "Stoxx 600": "quote/etr/EXSA",
       "DAX": "quote/etr/EXS1", "CAC 40": "quote/epa/CAC", "FTSE MIB": "quote/bit/ETFMIB", "SMI": "quote/swx/CSSMI",
       "FTSE 100": "quote/lon/ISF", "Nikkei 225": "quote/tyo/1321", "Taiex": "quote/tpe/0050", "Kospi": "quote/krx/069500",
       "Hang Seng": "quote/hkg/2800", "CSI 300": "quote/sha/510300"}
MES = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
out = dict(fecha=F, etf={k: v.split("/")[-1].upper() for k, v in ETF.items()}, precios={}, fechas={}, var={}, d200={}, fallos=[])
for k, p in ETF.items():
    try:
        s = urllib.request.urlopen(urllib.request.Request("https://stockanalysis.com/%s/" % p, headers=UA), timeout=40).read().decode()
        q = dict(re.findall(r'(\w+):("[^"]*"|[-\d.e]+)', re.search(r"quote:\{([^}]*)\}", s).group(1)))
        # precio de cierre de la sesión regular (no el de fuera de hora)
        px = float(q["p"]); out["precios"][k] = px; out["var"][k] = round(float(q["cp"]), 2) if "cp" in q else None
        td = q.get("td", "").strip('"')
        if not td:
            m = re.search(r'(\w{3}) (\d+), (\d{4})', q.get("u", ""))
            td = "%s-%02d-%02d" % (m.group(3), MES[m.group(1)], int(m.group(2))) if m else None
        out["fechas"][k] = td
        # 23/11: % sobre su media de 200 sesiones (serie diaria de 1 año de la misma página), para la fuerza relativa del modelo
        cl = [float(a) for a, b in re.findall(r'\{c:([-\d.]+),t:(\d{9,10})\}', s)]
        if len(cl) >= 200: out["d200"][k] = round((px / (sum(cl[-200:]) / 200) - 1) * 100, 2)
    except Exception as e: out["fallos"].append("%s: %s" % (k, e))
    time.sleep(1)
json.dump(out, open("bench.json", "w"), ensure_ascii=False, indent=1)
hp = "bench_hist.json"; Hh = json.load(open(hp)) if os.path.exists(hp) else {}
Hh[F] = dict(precios=out["precios"], fechas=out["fechas"]); json.dump(Hh, open(hp, "w"), ensure_ascii=False)
print("bench %s: %d de %d índices%s" % (F, len(out["precios"]), len(ETF), (" · fallos: " + "; ".join(out["fallos"])) if out["fallos"] else ""))
