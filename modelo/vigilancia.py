"""Vigilancia de posiciones compradas según el modelo (cartera real y simulador), a las 08:00 después de v3.py.
Entrada: posiciones.json = [{origen: "real"|"simulador", t: símbolo o ticker, n: nombre, senal?: estado del modelo al comprar ("Rebote confirmado" usa su salida propia), fecha: AAAA-MM-DD, precio: precio de compra, precioActual?: precio de hoy en la misma divisa (obligatorio en la cartera real, en euros)}]
(lo prepara la rutina con carteras/<uid>/operaciones y carteras/<uid>/simops).
Compara con el estado de ayer (vigilancia_estado.json) y solo avisa de lo NUEVO:
  SALIR    – nota de riesgo ≥ 70 o tendencia de fondo rota (en compras por «Rebote confirmado»: nuevo mínimo de 52 semanas o su stop por volatilidad)
  REVISAR  – la nota de oportunidad cae por debajo de 50 · pierde más que su stop por volatilidad (v3.2: 0,25 × amplitud de 52 sem., entre 8 y 25 %) · cumple 3 meses
  AVISO    – el mercado de su zona pasa de favorable a desfavorable (no obliga a vender: el objetivo es batir a su índice)
Salida: imprime JSON {avisos: [...], resumen: [...]} y actualiza vigilancia_estado.json"""
import json, os, sys, datetime as dt
from rutas import H, DATOS
F = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat(); HOY = dt.date.fromisoformat(F)
P = json.load(open("posiciones.json")) if os.path.exists("posiciones.json") else []
V = json.load(open("v3_raw.json")); RG = json.load(open("regimen.json")); FI = json.load(open("fichas3.json"))["fichas"]
O = {x["sa"]: x for x in V["O"]}; R = {x["sa"]: x for x in V["R"]}
TK = {}
for sa in O: TK.setdefault(sa.split("/")[-1], sa)
ALIAS = {"HOME": "bme/HOME"}
try: ALIAS.update(json.load(open("simprecios.json")).get("alias", {}))
except Exception: pass
ST = json.load(open("vigilancia_estado.json")) if os.path.exists("vigilancia_estado.json") else {}
def zona(o):
    p = o.get("pais")
    return p if p in ("EE. UU.", "España", "Japón") else "Asia (Taiwán, Corea, Hong Kong, China)" if p in ("Taiwán", "Corea", "Hong Kong/China", "China") else "Europa"
avisos, resumen, nuevo = [], [], {}
for p in P:
    sa = p["t"] if p["t"] in O else ALIAS.get(p["t"]) if ALIAS.get(p["t"]) in O else TK.get(p["t"])
    key = p["origen"] + ":" + p["t"]
    if not sa:
        resumen.append("%s (%s): fuera del modelo (ETF o valor fuera del universo); solo se vigila el precio." % (p["n"], p["origen"])); continue
    o, r = O[sa], R[sa]; z = RG["zonas"].get(zona(o), {})
    # margen para quien ya tiene la acción: la tendencia se da por rota con más de un 10 % bajo la media de 200 (la entrada exige −8 %) o en tendencia bajista
    tend = not ((o.get("d200") is not None and o["d200"] < -10) or o.get("rg") == "bajista")
    ahora = p.get("precioActual") or o["precio"]      # cartera real: precio en euros de precios/<TICKER> (misma divisa que la compra)
    var = (ahora / p["precio"] - 1) * 100 if p.get("precio") else None
    dias = (HOY - dt.date.fromisoformat(p["fecha"])).days if p.get("fecha") else None
    rebote = p.get("senal") == "Rebote confirmado"
    min52 = bool(o.get("precio") and FI.get(sa, {}).get("l52") and o["precio"] <= FI[sa]["l52"] * 1.005)
    s = dict(salirR=r["puntuacion"] >= 70, salirT=(not tend) and not rebote, min52=min52, nota50=o["puntuacion"] < 50, perd10=var is not None and var <= -(o.get("stop") or 10), tres=dias is not None and dias >= 91, mkt=bool(z.get("ok")))
    a = ST.get(key, {})
    def nuevo_(k): return s[k] and not a.get(k)
    if nuevo_("salirR"): avisos.append(("SALIR", "%s (%s): señal de venta del modelo (riesgo %d)." % (p["n"], p["origen"], r["puntuacion"])))
    if nuevo_("salirT"): avisos.append(("SALIR", "%s (%s): tendencia de fondo rota (%s %% respecto a su media de 200)." % (p["n"], p["origen"], ("%+.0f" % (o.get("d200") or 0)))))
    if nuevo_("min52"): avisos.append(("SALIR" if rebote else "REVISAR", "%s (%s): marca un nuevo mínimo de 52 semanas%s." % (p["n"], p["origen"], " (salida de la señal de rebote)" if rebote else "")))
    if nuevo_("nota50") and not rebote: avisos.append(("REVISAR", "%s (%s): la nota de oportunidad baja a %d." % (p["n"], p["origen"], o["puntuacion"])))
    if nuevo_("perd10"): avisos.append(("SALIR" if rebote else "REVISAR", ("%s (%s): pierde un %.1f %% desde la compra (su stop por volatilidad es −%d %%)%s." % (p["n"], p["origen"], -var, o.get("stop") or 10, "; salida de la señal de rebote" if rebote else "")).replace(".", ",", 1)))
    if nuevo_("tres"): avisos.append(("REVISAR", "%s (%s): cumple 3 meses, el plazo del modelo; toca decidir si se mantiene (nota hoy %d)." % (p["n"], p["origen"], o["puntuacion"])))
    if a.get("mkt") and not s["mkt"]: avisos.append(("AVISO", "%s (%s): el mercado de %s pasa a desfavorable (%s). No obliga a vender." % (p["n"], p["origen"], zona(o), z.get("dato", ""))))
    resumen.append("%s (%s): nota %d (%s), riesgo %d%s." % (p["n"], p["origen"], o["puntuacion"], o["estado"], r["puntuacion"], ("; %+.1f %% desde la compra" % var).replace(".", ",") if var is not None else ""))
    nuevo[key] = s
json.dump(nuevo, open("vigilancia_estado.json", "w"))
print(json.dumps({"avisos": [{"tipo": t, "texto": x} for t, x in avisos], "resumen": resumen}, ensure_ascii=False, indent=1))
