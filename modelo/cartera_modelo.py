"""Cartera automática del modelo (v3.2, desde el 21/11/2026).
Reglas fijas, sin intervención:
  COMPRA  cada valor que aparece con «Señal de compra» o «Rebote confirmado» y no está en cartera (nunca se pierde una señal).
  IMPORTE (24/11 12:21, decisión del dueño): SIEMPRE 100 € por compra, para medir cada operación igual. Una ganancia solo es real
          al vender. BOLSA COMÚN por grupo (modelo / experimental): cada compra se paga primero con la liquidez de las ventas (importe +
          beneficio ya realizado) y, si no llega, con dinero nuevo (se apunta como aportado): nunca se queda una señal sin comprar.
          Además se calcula el valor liquidativo (nav) como un fondo, solo para medir.
  VENTA   cuando el modelo da salida: riesgo ≥ 70, más de un 10 % bajo su media de 200 o tendencia bajista;
          en rebotes, nuevo mínimo de 52 semanas o pérdida mayor que su stop por volatilidad.
  EJECUCIÓN  (23/11, pedido del dueño) a la APERTURA de la primera sesión después del informe que da la señal: es el primer
          precio real al que se podría comprar tras leer el informe de las 08:00. No al cierre con el que se calculó la señal
          (eso sería mirar el futuro). Si falta la apertura, al cierre de esa sesión. Sin deslizamiento ni comisión (22/11).
Entradas: simprecios.json, ../cartera/datos/senales/<fecha>.json, fichas3.json. Estado: modelo_estado.json.
Salida: ../cartera/datos/modelo.json (lo lee la app). Uso: python3 cartera_modelo.py <fecha>"""
import json, sys, os, datetime as dt
from rutas import H, DATOS
F = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
TS = os.environ.get("SIM_TS") or F + "T08:00:00+01:00"
SP = json.load(open("simprecios.json")); FX = SP["fx"]; V = SP["valores"]; AL = SP.get("alias", {})
SEN_P = os.path.join(DATOS, "senales", F + ".json")
SEN = json.load(open(SEN_P)) if os.path.exists(SEN_P) else None
FI = json.load(open("fichas3.json"))["fichas"] if os.path.exists("fichas3.json") else {}
ST = json.load(open("modelo_estado.json")) if os.path.exists("modelo_estado.json") else dict(inicio=F, ops=[], pend=[], pos={}, hist=[], realizado=0.0)
IMPORTE, DESL = 100.0, 0.0   # 22/11: sin deslizamiento ni comisión, por decisión del dueño
def key(t): return t if t in V else AL.get(t) if AL.get(t) in V else None
def eur(v, campo="p"):
    f = FX.get("GBP") * 100 if v["d"] in ("GBX", "GBp") else FX.get(v["d"], 1 if v["d"] in ("€", "EUR") else None)
    return v[campo] / f if f and v.get(campo) else None
pos, pend = ST["pos"], ST["pend"]
BEN = (SEN or {}).get("bench") or {}   # 24/11: nivel del índice de referencia (ETF) al cierre de la sesión de la compra/venta, para comparar cada operación
def ben_en(fecha_ses, b):
    """nivel del índice b al cierre de la sesión fecha_ses: está en el archivo de señales del primer informe posterior"""
    d0 = os.path.join(DATOS, "senales")
    for f in sorted(os.listdir(d0)):
        if f[:10] > fecha_ses and f.endswith(".json") and len(f) == 15:
            try: return (json.load(open(os.path.join(d0, f))).get("bench") or {}).get(b)
            except Exception: return None
    return None
for k, p in pos.items():   # relleno de posiciones anteriores al 24/11
    if p.get("ib0") is None:
        p["b"] = p.get("b") or (V.get(k) or {}).get("b"); p["ib0"] = ben_en(p["fecha"], p["b"]) if p["b"] else None
esExp = lambda sn: sn == "Rebote confirmado"
gde = lambda sn: "experimental" if esExp(sn) else "modelo"
if "bolsa" not in ST:   # 24/11: paso a bolsa común; lo ya comprado cuenta como aportado, a 100 € la unidad
    ST["bolsa"] = {g: dict(caja=0.0, aportado=round(sum(p["coste"] for p in pos.values() if gde(p["senal"]) == g), 2)) for g in ("modelo", "experimental")}
    for g, b_ in ST["bolsa"].items(): b_["uds"] = b_["aportado"] / 100.0
def valg(g):
    t = 0.0
    for k, p in pos.items():
        if gde(p["senal"]) != g: continue
        v = V.get(k); pe = eur(v) if v else None; t += p["acc"] * pe if pe else p["coste"]
    return t
def nav(g):
    b_ = ST["bolsa"][g]; return (valg(g) + b_["caja"]) / b_["uds"] if b_["uds"] > 0 else 100.0
# 1) ejecutar las órdenes pendientes si ya hay un cierre posterior al de la señal
quedan = []
for o in pend:
    k = o["k"]; v = V.get(k)
    if not v or not v.get("f") or v["f"] <= o["f0"] or eur(v) is None: quedan.append(o); continue
    ap = v.get("o") if v.get("o") else None   # apertura de esa sesión; si no hay, cierre
    pe = eur(v, "o") if ap else eur(v); pl = ap or v["p"]; cuando = "apertura" if ap else "cierre"
    if o["tipo"] == "compra" and k not in pos:
        g = gde(o["senal"]); b_ = ST["bolsa"][g]; n0 = nav(g); imp_ = IMPORTE; o["importe"] = imp_   # 24/11 12:21: SIEMPRE 100 € por compra
        if b_["caja"] >= imp_: b_["caja"] -= imp_; o["aporte"] = 0.0
        else:
            ap_ = imp_ - b_["caja"]; b_["uds"] += ap_ / n0; b_["aportado"] = round(b_["aportado"] + ap_, 2); b_["caja"] = 0.0; o["aporte"] = round(ap_, 2)
        px = pe * (1 + DESL); acc = o["importe"] / px
        pos[k] = dict(n=v["n"], d=v["d"], r=v.get("r"), senal=o["senal"], fecha=v["f"], pxE=px, acc=acc, coste=o["importe"], px=pl, ejec=cuando, b=v.get("b"), ib0=BEN.get(v.get("b")))
        ST["ops"].append(dict(ts=TS, fecha=v["f"], k=k, n=v["n"], tipo="compra", senal=o["senal"], motivo=o["motivo"], px=pl, d=v["d"], pxE=round(px, 4), acciones=round(acc, 6), importe=o["importe"], aporte=o.get("aporte"), ejec=cuando))
    elif o["tipo"] == "venta" and k in pos:
        p = pos.pop(k); px = pe * (1 - DESL); imp = p["acc"] * px; res = imp - p["coste"]; ST["realizado"] += res
        ST["bolsa"][gde(p["senal"])]["caja"] += imp   # importe + beneficio vuelven a la bolsa común
        ST["ops"].append(dict(ts=TS, fecha=v["f"], k=k, n=v["n"], tipo="venta", senal=p["senal"], motivo=o["motivo"], px=pl, d=v["d"], ejec=cuando, pxE=round(px, 4), acciones=round(p["acc"], 6),
                              importe=round(imp, 2), resultado=round(res, 2), resultadoPct=round(res / p["coste"] * 100, 2), dias=(dt.date.fromisoformat(v["f"]) - dt.date.fromisoformat(p["fecha"])).days,
                              indice=p.get("b"), indicePct=(round((BEN[p["b"]] / p["ib0"] - 1) * 100, 2) if p.get("ib0") and BEN.get(p.get("b")) else None)))
pend = quedan
pk = {(o["k"], o["tipo"]) for o in pend}
# 2) nuevas señales de hoy → orden de compra para la siguiente apertura
if SEN:
    for x in SEN.get("op", []):
        if x.get("e") not in ("Señal de compra", "Rebote confirmado"): continue
        k = key(x["t"])
        if not k or k in pos or (k, "compra") in pk: continue
        reb = x["e"] == "Rebote confirmado"
        pend.append(dict(k=k, tipo="compra", senal=x["e"], f0=V[k]["f"], fecha=F, importe=IMPORTE,   # 22/11: 100 € en todas (también en rebotes), solo para ver subidas y bajadas en la misma escala
                         motivo="%s (nota %s)" % (x["e"], x.get("s"))))
        pk.add((k, "compra"))
# 3) salidas del modelo → orden de venta para la siguiente apertura
for k, p in pos.items():
    v = V.get(k)
    if not v or (k, "venta") in pk: continue
    pe = eur(v); var = (pe / p["pxE"] - 1) * 100 if pe else None
    m = None
    if p["senal"] == "Rebote confirmado":
        l52 = (FI.get(k) or {}).get("l52")
        if l52 and v["p"] <= l52 * 1.005: m = "nuevo mínimo de 52 semanas"
        elif var is not None and var <= -(v.get("st") or 10): m = "pierde un %.1f %% (stop −%d %%)" % (-var, v.get("st") or 10)
    # 24/11: un rebote se compra por definición bajo su media de 200 y con tendencia bajista; las salidas generales solo se
    # aplican cuando ya ha recuperado su media de 200 (como en el histórico). Hasta entonces, solo mínimo de 52 semanas o stop.
    if p["senal"] == "Rebote confirmado" and v.get("d2") is not None and v["d2"] >= 0: p["normal"] = True
    generales = p["senal"] != "Rebote confirmado" or p.get("normal")
    if not m and generales and (v.get("pr") or 0) >= 70: m = "señal de venta (riesgo %d)" % v["pr"]
    if not m and generales and v.get("d2") is not None and v["d2"] < -10: m = "tendencia rota (%+.0f %% vs. media de 200)" % v["d2"]
    if not m and generales and v.get("rgo") == "bajista": m = "tendencia bajista"
    if m: pend.append(dict(k=k, tipo="venta", f0=v["f"], fecha=F, motivo=m.replace(".", ","))); pk.add((k, "venta"))
# 4) valoración del día
out, inv, val = {}, 0.0, 0.0
for k, p in pos.items():
    v = V.get(k); pe = eur(v) if v else None
    vv = p["acc"] * pe if pe else p["coste"]
    out[k] = dict(n=p["n"], d=p["d"], r=p.get("r"), senal=p["senal"], fecha=p["fecha"], acc=round(p["acc"], 6), pxE=round(p["pxE"], 4), coste=round(p["coste"], 2),
                  px=v["p"] if v else None, val=round(vv, 2), ret=round((vv / p["coste"] - 1) * 100, 2), stop=(v or {}).get("st"), nota=(v or {}).get("po"), riesgo=(v or {}).get("pr"),
                  salida=next((o["motivo"] for o in pend if o["k"] == k and o["tipo"] == "venta"), None),
                  indice=p.get("b"), indicePct=(round((BEN[p["b"]] / p["ib0"] - 1) * 100, 2) if p.get("ib0") and BEN.get(p.get("b")) else None))
    inv += p["coste"]; val += vv
def medidas(g):
    e = g == "experimental"; C = [o for o in ST["ops"] if o["tipo"] == "venta" and esExp(o.get("senal")) == e]
    A_ = [p for p in out.values() if esExp(p["senal"]) == e]
    r = [o["resultadoPct"] for o in C]; gg = [x for x in r if x > 0]; ll = [x for x in r if x <= 0]
    anos = sum(max(o.get("dias") or 1, 1) for o in C) / 365.0
    ix = [(o["resultadoPct"], o["indicePct"]) for o in C if o.get("indicePct") is not None]
    srt = sorted(r)
    m = dict(cerradas=len(C), ganan=round(len(gg) / len(r) * 100, 1) if r else None, media=round(sum(r) / len(r), 2) if r else None,
             mediana=round((srt[len(srt) // 2] + srt[(len(srt) - 1) // 2]) / 2, 2) if r else None,
             ganMedia=round(sum(gg) / len(gg), 2) if gg else None, perdMedia=round(sum(ll) / len(ll), 2) if ll else None,
             ratio=round((sum(gg) / len(gg)) / -(sum(ll) / len(ll)), 2) if gg and ll and sum(ll) < 0 else None,
             porAno=round(sum(r) / anos, 1) if r and anos > 0 else None, peor=round(min(r), 2) if r else None,
             baten=round(sum(1 for a_, b_ in ix if a_ > b_) / len(ix) * 100, 1) if ix else None, exMedio=round(sum(a_ - b_ for a_, b_ in ix) / len(ix), 2) if ix else None,
             abiertas=len(A_), abiertasMedia=round(sum(p["ret"] for p in A_) / len(A_), 2) if A_ else None,
             abiertasIndice=round(sum(p["indicePct"] for p in A_ if p.get("indicePct") is not None) / max(1, sum(1 for p in A_ if p.get("indicePct") is not None)), 2) if any(p.get("indicePct") is not None for p in A_) else None,
             peorAbierta=round(min(p["ret"] for p in A_), 2) if A_ else None)
    return m
def grupo(g):   # 23/11: modelo y experimental por separado (páginas distintas en la app)
    e = g == "experimental"; P_ = [p for p in out.values() if esExp(p["senal"]) == e]
    b_ = ST["bolsa"][g]; vp = sum(p["val"] for p in P_)
    return dict(posiciones=len(P_), enPosiciones=round(vp, 2), caja=round(b_["caja"], 2), aportado=b_["aportado"], valor=round(vp + b_["caja"], 2),
                invertido=b_["aportado"], nav=round((vp + b_["caja"]) / b_["uds"], 4) if b_["uds"] else 100.0,
                unidad=IMPORTE, latente=round(vp - sum(p["coste"] for p in P_), 2),
                realizado=round(sum(o.get("resultado", 0) for o in ST["ops"] if o["tipo"] == "venta" and esExp(o.get("senal")) == e), 2), medidas=medidas(g))
ST["hist"] = [h for h in ST["hist"] if h["fecha"] != F] + [dict(fecha=F, invertido=round(inv, 2), valor=round(val, 2), realizado=round(ST["realizado"], 2),
                                                               g={g: grupo(g) for g in ("modelo", "experimental")})]
ST["pend"] = pend
json.dump(ST, open("modelo_estado.json", "w"), ensure_ascii=False, indent=1)
ventas = [o for o in ST["ops"] if o["tipo"] == "venta"]
res = dict(actualizado=TS, fecha=F, inicio=ST["inicio"], reglas=dict(importe=IMPORTE, importeRebote=IMPORTE, deslizamiento=DESL, bolsa="común desde el 24/11: cada compra SIEMPRE de 100 €, pagada con la liquidez de las ventas (beneficio realizado incluido) y, si no llega, con dinero nuevo",
           compra="«Señal de compra» o «Rebote confirmado» (mitad en rebotes)", venta="riesgo ≥ 70, más de un 10 % bajo su media de 200 o tendencia bajista; en rebotes, nuevo mínimo de 52 semanas o su stop",
           ejecucion="a la apertura de la sesión siguiente al informe que da la señal (si falta, al cierre), sin comisión ni deslizamiento"),
           resumen=dict(posiciones=len(out), invertido=round(inv, 2), valor=round(val, 2), latente=round(val - inv, 2), realizado=round(ST["realizado"], 2),
                        cerradas=len(ventas), ganadoras=sum(1 for o in ventas if o["resultado"] > 0)),
           grupos={g: grupo(g) for g in ("modelo", "experimental")},
           pos=out, pend=[dict(k=o["k"], n=(V.get(o["k"]) or {}).get("n"), tipo=o["tipo"], senal=o.get("senal") or (pos.get(o["k"]) or {}).get("senal"), motivo=o["motivo"], fecha=o["fecha"], importe=(IMPORTE if o["tipo"] == "compra" else o.get("importe"))) for o in pend],
           ops=ST["ops"][-200:], hist=ST["hist"])
json.dump(res, open(os.path.join(DATOS, "modelo.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print("cartera del modelo %s: %d posiciones, %d pendientes (%s), invertido %.2f, valor %.2f, realizado %.2f" % (
    F, len(out), len(pend), ", ".join("%s %s" % (o["tipo"], o["k"]) for o in pend), inv, val, ST["realizado"]))
