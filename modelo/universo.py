"""Universo del modelo con una regla fija (sin elegir a mano), a partir de las listas de StockAnalysis de
mayores empresas por país (solo la cotización principal de cada empresa) y del S&P 500:
v4 (22/11/2026, pedido del dueño: «analizar al completo» los índices): EE. UU. = S&P 500 + Nasdaq 100 completos ·
España 35 (≈ IBEX 35) · Europa: las 50 mayores de la eurozona (≈ Euro Stoxx 50) + resto de Europa hasta 120 (Reino Unido, Suiza, nórdicos) ·
Japón 225 (≈ Nikkei 225) · China continental 300 (≈ CSI 300, Shanghái + Shenzhen) · Taiwán 150 · Corea 200 (≈ KOSPI 200) · Hong Kong 25.
Salvo S&P 500 y Nasdaq 100 (listas oficiales), los índices se aproximan con las mayores por capitalización de su bolsa.
Orden por capitalización en dólares. Se quitan duplicados (otra clase de acción de la misma empresa).
Salida: universo.json [{sa, n, region, pais, bolsa, mcUSD}]  (se recalcula una vez por semana: lunes 08:00)"""
import urllib.request, re, json, os, time
from rutas import H, DATOS
UA = {"User-Agent": "cartera-inversiomes/1.0 (uso personal; consulta diaria)"}
row = re.compile(r'\{no:\d+,s:"([^"]+)",n:"((?:[^"\\]|\\.)*)"([^{}]*?)\}')
def lista(slug):
    s = urllib.request.urlopen(urllib.request.Request("https://stockanalysis.com/list/%s/" % slug, headers=UA), timeout=40).read().decode()
    time.sleep(1.5); out = []
    for sym, n, rest in row.findall(s):
        try: n = json.loads('"' + n + '"')
        except Exception: pass
        m = re.search(r"marketCap(?:USD)?:([\d.e+]+)", rest)
        if "isPrimaryListing:false" in rest: continue
        if "subtype:" in rest and 'subtype:"stock"' not in rest: continue
        out.append(dict(sa=sym, n=n, mc=float(m.group(1)) / 1e9 if m else 0))
    return out
SUF = re.compile(r"\b(inc|corp|corporation|co|company|ltd|limited|plc|ag|se|sa|s\.a|nv|n\.v|spa|s\.p\.a|ab|asa|oyj|holdings?|group|the|class [a-z]|adr|aktiengesellschaft)\b\.?")
norm = lambda n: re.sub(r"[^a-z0-9]", "", SUF.sub("", n.lower().replace("&", "and")))
BOLSA = {"bme": "BME", "etr": "Xetra", "epa": "Euronext París", "ams": "Euronext Ámsterdam", "bit": "Borsa Italiana", "swx": "Suiza", "lon": "Londres",
         "cph": "Copenhague", "sto": "Estocolmo", "ebr": "Euronext Bruselas", "hel": "Helsinki", "osl": "Oslo", "lis": "Euronext Lisboa",
         "tyo": "Tokio", "tpe": "Taiwán", "krx": "Corea", "hkg": "Hong Kong", "sha": "Shanghái", "she": "Shenzhen"}
seen, out = set(), []
def add(r, region, pais):
    nk = norm(r["n"])
    if not nk or nk in seen: return False
    seen.add(nk); ex = r["sa"].split("/")[0] if "/" in r["sa"] else ""
    out.append(dict(sa=r["sa"], n=r["n"], region=region, pais=pais, bolsa=BOLSA.get(ex, "EE. UU." if not ex else ex), mcUSD=round(r["mc"], 1)))
    return True
ORDINARIA = lambda r: not (r["sa"].startswith("krx/") and not r["sa"].endswith("0")) and not (r["sa"].startswith("tpe/") and not (r["sa"][4:].isdigit() and len(r["sa"]) == 8)) \
    and not __import__("re").search(r"\b(pref|preferred|prefer)\b", r["n"], __import__("re").I)   # 23/11: fuera preferentes y certificados (duplican empresas)
def take(rows, n, region, pais, filt=lambda r: True):
    k = 0
    for r in sorted([r for r in rows if filt(r) and ORDINARIA(r)], key=lambda r: -r["mc"]):
        if add(r, region, r.get("pais", pais)): k += 1
        if k >= n: break
take(lista("sp-500-stocks"), 600, "EE. UU.", "EE. UU.")
take(lista("nasdaq-100-stocks"), 150, "EE. UU.", "EE. UU.")
take(lista("largest-companies-in-spain"), 35, "España", "España", lambda r: r["sa"].startswith("bme/"))
EUR = []
EZ = {"Alemania", "Francia", "Países Bajos", "Italia", "Bélgica", "Finlandia", "Portugal", "Irlanda", "Austria"}
for c, p in (("germany", "Alemania"), ("france", "Francia"), ("the-netherlands", "Países Bajos"), ("italy", "Italia"), ("switzerland", "Suiza"), ("the-uk", "Reino Unido"),
             ("denmark", "Dinamarca"), ("sweden", "Suecia"), ("belgium", "Bélgica"), ("finland", "Finlandia"), ("norway", "Noruega"), ("portugal", "Portugal")):
    EUR += [dict(r, pais=p) for r in lista("largest-companies-in-" + c) if "/" in r["sa"] and r["sa"].split("/")[0] in BOLSA]
take(EUR, 50, "Resto del mundo", None, lambda r: r["pais"] in EZ)      # ≈ Euro Stoxx 50
take(EUR, 70, "Resto del mundo", None)                                 # resto de Europa (incluye Reino Unido y Suiza)
for slug, n, p, ex in (("largest-companies-in-japan", 225, "Japón", "tyo/"), ("largest-companies-in-taiwan", 150, "Taiwán", "tpe/"),
                       ("largest-companies-in-south-korea", 200, "Corea", "krx/")):
    xl = {"tyo/": "tokyo-stock-exchange", "tpe/": "taiwan-stock-exchange", "krx/": "korea-stock-exchange"}[ex]
    take(lista(slug) + lista(xl), n, "Resto del mundo", p, lambda r, ex=ex: r["sa"].startswith(ex))
CN = lista("shanghai-stock-exchange") + lista("shenzhen-stock-exchange") + lista("largest-companies-in-china")
take(CN, 300, "Resto del mundo", "China", lambda r: r["sa"].startswith(("sha/", "she/")))   # ≈ CSI 300
take(lista("largest-companies-in-hong-kong") + lista("largest-companies-in-china"), 25, "Resto del mundo", "Hong Kong/China", lambda r: r["sa"].startswith("hkg/"))
# 23/11 (pedido del dueño): las acciones de la cartera real se analizan SIEMPRE para la vigilancia, aunque no entren en el universo.
# Van marcadas cartera=True: no salen en Oportunidades/Riesgo ni dan señales a la cartera del modelo.
REG = {"ES": ("España", "España", "bme/"), "US": ("EE. UU.", "EE. UU.", "")}
if os.path.exists(os.path.join(H, "cartera.json")):
    have = {x["sa"] for x in out}
    for t, p in json.load(open(os.path.join(H, "cartera.json"))).items():
        isin = p.get("isin") or ""
        if isin[:2] not in REG: continue          # los ETF (IE, LU) no son acciones: fuera del modelo
        region, pais, pre = REG[isin[:2]]; sa = pre + t
        if sa in have: continue
        out.append(dict(sa=sa, n=p.get("nombre") or t, region=region, pais=pais, bolsa=BOLSA.get(pre.rstrip("/"), "EE. UU."), mcUSD=0, cartera=True))
json.dump(out, open(os.path.join(H, "universo.json"), "w"), ensure_ascii=False, indent=0)
from collections import Counter
print(len(out), Counter(x["pais"] for x in out).most_common())
