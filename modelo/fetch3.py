"""Fichas diarias del universo (universo.json) desde StockAnalysis, consulta directa y pausada (~1 por segundo).
- Todas las cifras de la página de estadísticas (109 campos) + cotización (precio, fecha, máximo y mínimo de 52 semanas).
- Sector e industria desde la página principal; se guardan en sectores.json y solo se piden para valores nuevos.
- Archivo diario "tal como estaba ese día" en archivo/<fecha>.json.gz (base para medir revisiones de
  estimaciones, cambios de objetivo y, con el tiempo, una prueba hacia atrás con datos de cada fecha).
Uso: python3 fetch3.py <fecha>  → fichas3.json"""
import urllib.request, re, html, json, sys, os, time, gzip, datetime as dt
from rutas import H, DATOS
F = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
UA = {"User-Agent": "cartera-inversiomes/1.0 (uso personal; consulta diaria)"}
U = json.load(open("universo.json"))
SEC = json.load(open("sectores.json")) if os.path.exists("sectores.json") else {}
def get(u):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404: raise
            time.sleep(5 * (i + 1))
        except Exception: time.sleep(5 * (i + 1))
    raise RuntimeError("sin respuesta")
def base(sa): return "https://stockanalysis.com/" + ("quote/%s/" % sa if "/" in sa else "stocks/%s/" % sa.lower())
def num(v):
    if v is None: return None
    v = html.unescape(str(v)).replace("$", "").replace(",", "").replace("+", "").strip()
    mult = 1
    if v[-1:] in "KMBT" and v[:-1].replace(".", "").replace("-", "").isdigit(): mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[v[-1]]; v = v[:-1]
    if v.endswith("%"): v = v[:-1]
    try: return float(v) * mult
    except Exception: return None
out, fallos = {}, []
for i, x in enumerate(U):
    sa = x["sa"]
    try:
        s = get(base(sa) + "statistics/")
        d = {a: (c or b) for a, _, b, c in re.findall(r'\{id:"([^"]+)",title:"([^"]+)",value:("([^"]*)"|[^,}]+)', s)}
        q = re.search(r"quote:\{([^}]*)\}", s)
        if not q: raise ValueError("sin cotización")
        qq = dict(re.findall(r'(\w+):("[^"]*"|[-\d.e]+)', q.group(1)))
        r = {k: num(v) for k, v in d.items() if k not in ("analystRatings", "earningsdate", "exdivdate", "lastSplitDate", "lastSplitType", "splitRatio")}
        r.update(cons=html.unescape(d.get("analystRatings", "")) or None, earningsdate=d.get("earningsdate"),
                 px=float(qq["p"]), pxo=num(qq.get("o")), fecha=qq.get("td", '""').strip('"'), h52=num(qq.get("h52")), l52=num(qq.get("l52")))
        cur = re.search(r'curr:\{main:"(\w+)",price:"(\w+)"', s)
        r["divisa"] = cur.group(2) if cur else None
        if sa not in SEC:
            time.sleep(1.0); p = get(base(sa))
            sec = re.search(r'\{t:"Sector",v:"([^"]+)"', p); ind = re.search(r'\{t:"Industry",v:"([^"]+)"', p)
            SEC[sa] = [html.unescape(sec.group(1)) if sec else None, html.unescape(ind.group(1)) if ind else None]
        r["sector"], r["industria"] = SEC.get(sa, [None, None])
        out[sa] = r
    except Exception as e:
        fallos.append("%s: %s" % (sa, e))
    time.sleep(1.0)
    if i % 50 == 49:
        json.dump(SEC, open("sectores.json", "w"), ensure_ascii=False); print(i + 1, "…", flush=True)
json.dump(SEC, open("sectores.json", "w"), ensure_ascii=False)
json.dump({"fecha": F, "fichas": out}, open("fichas3.json", "w"), ensure_ascii=False)
os.makedirs("archivo", exist_ok=True)
with gzip.open("archivo/%s.json.gz" % F, "wt") as fh: json.dump({"fecha": F, "fichas": out}, fh, ensure_ascii=False)
print("ok", len(out), "fichas; fallos", len(fallos), fallos[:10])
sys.exit(2 if len(fallos) > 0.05 * len(U) else 0)   # más de un 5 % de fallos: diario.sh lo reintenta una vez
