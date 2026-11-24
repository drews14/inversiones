"""Fondos indexados (ETF/ETC) del dueño: rendimiento, riesgo, tendencia, patrones y vista DCA. Pedido del dueño 22/11/2026.
Fuente: página de cotización de StockAnalysis (gratuita): último cierre, cambios (1 sem … 5 años), rentabilidad total anualizada,
comisión (TER), patrimonio, nº de posiciones y la serie diaria de 1 año. Sin recomendaciones: solo datos.
Entrada: cartera.json (posiciones reales; ops2cartera.py) y precios de la base de datos que se pasan en precios.json opcional.
Salida: ../cartera/datos/fondos.json y fondos_hist.json (serie propia diaria). Uso: python3 fondos.py <fecha>"""
import urllib.request, re, json, os, sys, time, math, statistics as st, datetime as dt
from rutas import H, DATOS
F = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
UA = {"User-Agent": "cartera-inversiomes/1.0"}
# ISIN → cotización de StockAnalysis (la misma clase/moneda que en Trade Republic cuando existe; oro y plata, en Londres en USD)
SA = {"IE00BYTRRD19": ("etr/SPFT", "EUR"), "IE00B4L5Y983": ("etr/EUNL", "EUR"), "IE00BKM4GZ66": ("etr/IS3N", "EUR"),
      "IE000OJ5TQP4": ("etr/ASWC", "EUR"), "LU2023678449": ("epa/MILL", "EUR"), "IE00B4ND3602": ("lon/IGLN", "USD"),
      "IE00B4NCWG09": ("lon/ISLN", "USD")}
INFO = {"IE00BYTRRD19": "Tecnología mundial (MSCI World IT)", "IE00B4L5Y983": "Bolsa mundial desarrollada (MSCI World)",
        "IE00BKM4GZ66": "Emergentes con pequeñas (MSCI EM IMI)", "IE000OJ5TQP4": "Defensa (EE. UU. y Europa)",
        "LU2023678449": "Deporte y eSports (Solactive Sports & eSports)", "IE00B4ND3602": "Oro físico", "IE00B4NCWG09": "Plata física"}
# Cambios del propio fondo que hay que contar (comprobados en fuentes públicas)
NOMBRE = {"LU2023678449": "Amundi Global Sport and eSport (antes MSCI Millennials)"}
AVISO = {"LU2023678449": "Desde el 22/10/2026 este fondo ya no es el MSCI Millennials: Amundi le cambió el índice al Solactive Sports & eSports y el nombre a «Global Sport and eSport». Lo de dentro es otro (deporte y videojuegos). Las rentabilidades de más de un mes mezclan el índice antiguo y el nuevo."}
MES = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
POS = json.load(open("cartera.json")) if os.path.exists("cartera.json") else {}
def get(u):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode()
        except Exception: time.sleep(4 * (i + 1))
    raise RuntimeError("sin respuesta")
def fnum(x):
    try: return float(str(x).replace("%", "").replace("+", "").replace(",", ""))
    except Exception: return None
out, series, fallos = {}, {}, []
for t, p in POS.items():
    isin = p.get("isin")
    if isin not in SA: continue
    sym, mon = SA[isin]
    try:
        s = get("https://stockanalysis.com/quote/%s/" % sym)
        q = dict(re.findall(r'(\w+):("[^"]*"|[-\d.e]+)', re.search(r"quote:\{([^}]*)\}", s).group(1)))
        px = float(q["p"]); fecha = q.get("td", '""').strip('"')
        ch = dict((k, float(v)) for k, v in re.findall(r'(price1w|price1m|price3m|price6m|priceYTD|price1y|price5y|priceMAX):([-\d.]+)', s))
        pf = dict((k, float(v)) for k, v in re.findall(r'(tr1m|trYTD|tr1y|cagr5y|cagr10y|cagrMAX):([-\d.]+)', s[s.find("performance:{"):s.find("performance:{") + 400]))
        ter = re.search(r'expenseRatio:"([^"]+)"', s); aum = re.search(r'aum:"([^"]+)"', s); nh = re.search(r'holdings:(\d+)', s); inc = re.search(r'inception:"([^"]+)"', s)
        pts = [(dt.datetime.fromtimestamp(int(b), dt.timezone.utc).date().isoformat(), float(a)) for a, b in re.findall(r'\{c:([-\d.]+),t:(\d{9,10})\}', s)]
        pts = dict(pts)
        if fecha < F: pts[fecha] = px
        # 24/11: la cabecera de la página puede quedarse días atrás (SPFT seguía en el 20/11): se completa con la página /history/
        # y se usa el último cierre de una sesión ANTERIOR a hoy (las filas de hoy son de la sesión en curso).
        try:
            time.sleep(1.2)
            hh = get("https://stockanalysis.com/quote/%s/history/" % sym)
            for d0, c0 in re.findall(r'\{t:"(\d{4}-\d{2}-\d{2})",o:[-\d.]+,h:[-\d.]+,l:[-\d.]+,c:([-\d.]+)', hh):
                if d0 < F: pts[d0] = float(c0)
        except Exception as e: fallos.append("%s historial: %s" % (t, e))
        pts = sorted((d0, c0) for d0, c0 in pts.items() if d0 < F)
        if pts: fecha, px = pts[-1]
        def atras(dias):
            lim = (dt.date.fromisoformat(fecha) - dt.timedelta(days=dias)).isoformat(); c = [c0 for d0, c0 in pts if d0 <= lim]
            return c[-1] if c else None
        prevano = [c0 for d0, c0 in pts if d0 < fecha[:4] + "-01-01"]
        base = dict(price1w=atras(7), price1m=atras(30), price3m=atras(91), price6m=atras(182), price1y=atras(365), priceYTD=prevano[-1] if prevano else None)
        for k0, v0 in base.items():
            if v0: ch[k0] = v0
        v = [c for _, c in pts]
        rets = [math.log(v[i] / v[i - 1]) for i in range(1, len(v)) if v[i - 1] > 0]
        vol = st.pstdev(rets) * math.sqrt(252) * 100 if len(rets) > 20 else None
        peak, mdd = 0, 0
        for c in v: peak = max(peak, c); mdd = min(mdd, c / peak - 1)
        ma200 = st.mean(v[-200:]) if len(v) >= 200 else None; ma50 = st.mean(v[-50:]) if len(v) >= 50 else None
        r = lambda k: round((px / ch[k] - 1) * 100, 2) if ch.get(k) else None
        # vista DCA: aportación fija a primeros de cada mes durante el último año (con la serie diaria) frente a comprarlo todo hace 1 año
        meses, vis = [], set()
        for d, c in pts:
            if d[:7] not in vis: vis.add(d[:7]); meses.append(c)
        meses = meses[-12:]
        dca = round((px * sum(1 / c for c in meses) / len(meses) - 1) * 100, 2) if len(meses) >= 6 else None
        h52 = max([x for x in [fnum(q.get("h52"))] + v[-260:] if x]) if v else fnum(q.get("h52")); l52 = min([x for x in [fnum(q.get("l52"))] + v[-260:] if x]) if v else fnum(q.get("l52"))
        # composición: principales posiciones, sectores y países (página /holdings/); oro y plata, 100 % metal
        comp = None
        if isin in ("IE00B4ND3602", "IE00B4NCWG09"):
            met = "Oro" if isin == "IE00B4ND3602" else "Plata"
            comp = dict(top=[[met, met, 100.0]], sectores=[["Metales preciosos", 100.0]], paises=[["Materias primas", 100.0]], cubierto=100.0)
        else:
            time.sleep(1.2)
            try:
                hs = get("https://stockanalysis.com/quote/%s/holdings/" % sym)
                top = [[a.lstrip("$@").split("-")[-1].split(":")[-1], n, float(w)] for a, n, w in re.findall(r'\{no:\d+,s:"([^"]*)",n:"([^"]*)",holdingWeight:([-\d.]+)', hs)]
                sec = [[n, float(w)] for n, w in re.findall(r'\{n:"([^"]+)",w:([-\d.]+)\}', hs[hs.find("sectors:["):hs.find("]", hs.find("sectors:["))])]
                pai = [[c, float(w)] for w, c in re.findall(r'weight:([-\d.]+),country:"([^"]+)"', hs[hs.find("countries:["):hs.find("]", hs.find("countries:["))])]
                fd = re.search(r'lazyColumnMeta:"quote",date:"(\w{3}) (\d+), (\d{4})"', hs)
                comp = dict(top=top[:60], sectores=sec, paises=pai, cubierto=round(sum(x[2] for x in top[:60]), 1),
                            fecha="%s-%02d-%02d" % (fd.group(3), MES[fd.group(1)], int(fd.group(2))) if fd else None)
            except Exception as e: fallos.append("%s composición: %s" % (t, e))
        out[t] = dict(nombre=NOMBRE.get(isin, p.get("nombre")), aviso=AVISO.get(isin), isin=isin, cotizacion=sym.upper().replace("/", ":"), moneda=mon, que=INFO.get(isin), precio=px, fecha=fecha,
                      r1s=r("price1w"), r1m=r("price1m"), r3m=r("price3m"), r6m=r("price6m"), rytd=r("priceYTD"), r1a=r("price1y"), r5a=r("price5y"),
                      cagr5=pf.get("cagr5y"), cagr10=pf.get("cagr10y"), cagrMax=pf.get("cagrMAX"), inicio=inc.group(1) if inc else None,
                      ter=ter.group(1) if ter else None, patrimonio=aum.group(1) if aum else None, posiciones=int(nh.group(1)) if nh else None,
                      vol=round(vol, 1) if vol else None, maxCaida1a=round(mdd * 100, 1), desdeMax=round((px / h52 - 1) * 100, 1) if h52 else None,
                      h52=h52, l52=l52, vsMA200=round((px / ma200 - 1) * 100, 1) if ma200 else None, vsMA50=round((px / ma50 - 1) * 100, 1) if ma50 else None,
                      rangoMes=round(vol / math.sqrt(12), 1) if vol else None, comp=comp, serie=[[d, round(c, 4)] for d, c in pts[-260:]])
        series[t] = dict(pts)
    except Exception as e: fallos.append("%s: %s" % (t, e))
    time.sleep(1.2)
# patrones: correlación de las rentabilidades diarias del último año entre fondos
ks = list(series); corr = {}
for i, a in enumerate(ks):
    for b in ks[i + 1:]:
        ds = sorted(set(series[a]) & set(series[b]))
        ra = [math.log(series[a][ds[j]] / series[a][ds[j - 1]]) for j in range(1, len(ds))]
        rb = [math.log(series[b][ds[j]] / series[b][ds[j - 1]]) for j in range(1, len(ds))]
        if len(ra) > 60:
            try: corr[a + "|" + b] = round(st.correlation(ra, rb), 2)
            except Exception: pass
hp = "fondos_hist.json"; Hh = json.load(open(hp)) if os.path.exists(hp) else {}
Hh[F] = {t: x["precio"] for t, x in out.items()}; json.dump(Hh, open(hp, "w"))
ref = out.get("EUNL")
for t, x in out.items():   # cada fondo frente al MSCI World (EUNL), en puntos de rentabilidad
    x["vsMundo1a"] = round(x["r1a"] - ref["r1a"], 2) if ref and x.get("r1a") is not None and ref.get("r1a") is not None and t != "EUNL" else None
    x["vsMundoYtd"] = round(x["rytd"] - ref["rytd"], 2) if ref and x.get("rytd") is not None and ref.get("rytd") is not None and t != "EUNL" else None
CAMBIO = {"LU2023678449": "2026-10-21"}   # último cierre con el índice antiguo
def desde(x, d0):
    s = [c for d, c in x["serie"] if d >= d0]
    if len(s) < 2 or not [1 for d, c in x["serie"] if d == d0]: return None
    pk, mdd = s[0], 0
    for v in s: pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    return dict(desde=d0, ret=round((s[-1] / s[0] - 1) * 100, 2), maxCaida=round(mdd * 100, 2), sesiones=len(s) - 1)
for t, x in out.items():
    d0 = CAMBIO.get(x["isin"])
    if d0:
        dc = desde(x, d0); rm = desde(ref, d0) if ref else None
        if dc and rm: dc["mundo"] = rm["ret"]; dc["vsMundo"] = round(dc["ret"] - rm["ret"], 2)
        x["desdeCambio"] = dc
res = dict(fecha=F, actualizado=os.environ.get("SIM_TS") or F + "T08:00:00+01:00", fondos=out, correlaciones=corr, fallos=fallos,
           nota="Datos de StockAnalysis (cotización en %s; oro y plata en Londres, en dólares). Rentabilidades de precio; las de 5 y 10 años y desde el inicio son anualizadas con dividendos. Solo datos: no son recomendaciones." % "Xetra o Euronext")
json.dump(res, open(os.path.join(DATOS, "fondos.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print("fondos %s: %d fondos, %d correlaciones%s" % (F, len(out), len(corr), (" · fallos: " + "; ".join(fallos)) if fallos else ""))
