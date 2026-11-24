"""Una sola vez: trae el historial de la app de «Mi cartera» (señales diarias y cartera del modelo) para no empezar de cero.
Uso: python3 modelo/sembrar.py <carpeta datos de Mi cartera>   (la que tiene senales/ y modelo.json)"""
import json, os, sys, shutil, glob
from rutas import H, DATOS
SRC = os.path.abspath(sys.argv[1])
for p in glob.glob(os.path.join(SRC, "senales", "*.json")):
    d = os.path.join(DATOS, "senales", os.path.basename(p))
    if not os.path.exists(d): shutil.copy(p, d)
fechas = sorted(f[:-5] for f in os.listdir(os.path.join(DATOS, "senales")) if f.endswith(".json"))
json.dump({"fechas": fechas}, open(os.path.join(DATOS, "senales.json"), "w"))
for f in ("historico.json", "factores.json", "regiones.json", "fondos.json"):
    if os.path.exists(os.path.join(SRC, f)) and not os.path.exists(os.path.join(DATOS, f)): shutil.copy(os.path.join(SRC, f), DATOS)
if not os.path.exists("modelo_estado.json") and os.path.exists(os.path.join(SRC, "modelo.json")):
    m = json.load(open(os.path.join(SRC, "modelo.json")))
    sen = {}
    for f in fechas:   # fecha de los datos de cada señal (f0 de las órdenes pendientes)
        for x in json.load(open(os.path.join(DATOS, "senales", f + ".json"))).get("op", []): sen[(f, x["t"])] = x.get("f")
    pos = {k: dict(n=p["n"], d=p["d"], r=p.get("r"), senal=p["senal"], fecha=p["fecha"], pxE=p["pxE"], acc=p["acc"], coste=p["coste"],
                   px=p.get("px"), ejec="apertura", b=p.get("indice"), ib0=None) for k, p in m["pos"].items()}
    pend = [dict(k=o["k"], tipo=o["tipo"], senal=o.get("senal"), f0=sen.get((o["fecha"], o["k"])) or o["fecha"], fecha=o["fecha"],
                 importe=o.get("importe"), motivo=o["motivo"]) for o in m["pend"]]
    bolsa = {g: dict(caja=v["caja"], aportado=v["aportado"], uds=(v["valor"] / v["nav"]) if v.get("nav") else v["aportado"] / 100.0) for g, v in m["grupos"].items()}
    st = dict(inicio=m["inicio"], ops=m["ops"], pend=pend, pos=pos, hist=m["hist"], realizado=m["resumen"]["realizado"], bolsa=bolsa)
    json.dump(st, open("modelo_estado.json", "w"), ensure_ascii=False, indent=1)
    shutil.copy(os.path.join(SRC, "modelo.json"), DATOS)
    print("cartera del modelo: %d posiciones, %d órdenes pendientes" % (len(pos), len(pend)))
print("señales:", len(fechas), "días ->", DATOS)
