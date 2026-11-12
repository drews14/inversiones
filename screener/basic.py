"""Modo básico: explicaciones en lenguaje sencillo, sin cifras, para quien no sabe de bolsa."""
import re

SECTOR_ES = {
    "Technology": "tecnología",
    "Healthcare": "salud y farmacia",
    "Financial Services": "bancos y finanzas",
    "Consumer Cyclical": "consumo (tiendas, coches, ocio)",
    "Consumer Defensive": "productos básicos (alimentación, limpieza)",
    "Industrials": "industria",
    "Energy": "energía (petróleo, gas)",
    "Utilities": "electricidad, agua y gas",
    "Real Estate": "inmobiliario",
    "Basic Materials": "materias primas (metales, química)",
    "Communication Services": "telecomunicaciones y medios",
}

POS_WORDS = r"sube|suben|subida|dispara|récord|record|beneficio|mejora|supera|eleva|alza|gana|crece|crecimiento|impulsa|" \
            r"upgrade|beats?|surges?|soars?|rall(y|ies)|raises?|strong|growth|jumps?|gains?|outperform|bullish|buy"
NEG_WORDS = r"cae|caen|caída|desploma|pierde|pérdidas?|baja|recorta|rebaja|multa|investigaci[oó]n|demanda|alerta|" \
            r"hunde|plunges?|falls?|drops?|cuts?|downgrade|miss(es)?|lawsuit|probe|slump|weak|sell-?off|tumbles?|" \
            r"warning|declines?|bearish|crash"


GENERIC = {"inc", "corp", "corporation", "company", "group", "holdings", "holding", "the", "banco", "industria",
           "compañía", "compania", "international", "technologies", "technology", "systems", "sociedad", "anonima",
           "limited", "ltd", "plc", "co", "sa", "s.a.", "nv", "ag", "se", "de", "del", "y", "and", "&"}


COMMON_FIRST = {"western", "general", "american", "united", "first", "national", "global", "digital", "southern",
                "northern", "eastern", "applied", "advanced", "public", "royal", "new", "air", "east", "west", "central"}


def keywords(name):
    """Expresión que identifica a la empresa en un titular (p. ej. 'Adobe', 'Western Digital')."""
    words = [w for w in re.findall(r"[A-Za-zÀ-ÿ0-9&']+", str(name)) if w.lower() not in GENERIC and len(w) >= 2]
    if not words:
        return []
    if words[0].lower() in COMMON_FIRST and len(words) > 1:
        return [f"{words[0]} {words[1]}"]
    return [words[0]]


def relevant(items, name, ticker):
    kws = [k.lower() for k in keywords(name)] + [ticker.split(".")[0].lower()]
    out = []
    for it in items:
        t = (it.get("title") or "").lower()
        if any(re.search(rf"\b{re.escape(k)}\b", t) for k in kws if len(k) >= 3):
            out.append(it)
    return out


def news_tone(items):
    pos = neg = 0
    for it in items:
        t = (it.get("title") or "").lower()
        pos += len(re.findall(rf"\b({POS_WORDS})\b", t))
        neg += len(re.findall(rf"\b({NEG_WORDS})\b", t))
    if pos == neg == 0:
        return "neutras"
    if pos >= neg * 1.5:
        return "buenas"
    if neg >= pos * 1.5:
        return "malas"
    return "mixtas"


def volatility(close):
    c = close.dropna()
    if len(c) < 60:
        return None
    return float(c.pct_change().iloc[-120:].std() * (252 ** 0.5))


def company(r, info, close, news_es, bench_chg1m=None):
    """Devuelve el bloque 'basic' de una empresa."""
    b = r.get("blocks") or {}
    t = r.get("timing") or {}
    flags = " ".join(r.get("flags") or [])
    neg_sig = " ".join(t.get("negative") or [])
    pos_sig = " ".join(t.get("positive") or [])
    up = r.get("upside")
    n_an = r.get("analysts") or 0
    de = info.get("debtToEquity")
    margin = info.get("profitMargins")
    dy = info.get("dividendYield")
    vol = volatility(close)
    news_es = relevant(news_es, r.get("name"), r.get("ticker", ""))
    tone = news_tone(news_es + relevant(r.get("news") or [], r.get("name"), r.get("ticker", "")))

    yes, no = [], []
    if b.get("valuation", 0) >= 15:
        yes.append("Está más barata que otras empresas parecidas, comparando lo que cuesta con lo que gana.")
    if b.get("quality", 0) >= 17 and (margin or 0) > 0:
        yes.append("Es un negocio que gana dinero de forma sólida.")
    if up and up > 0.15 and n_an >= 5:
        yes.append("Los expertos que la siguen creen que su precio puede subir.")
    if (r.get("drawdown") or 0) < -0.2:
        yes.append("Ha bajado bastante en los últimos meses, así que ahora sale más barata que antes.")
    if t.get("label") == "giro":
        yes.append("Parece que ya ha dejado de caer y empieza a recuperarse.")
    if "subiendo previsiones" in pos_sig:
        yes.append("Los expertos esperan ahora que gane más dinero que hace unas semanas.")
    dy_pct = (dy * 100 if dy < 0.2 else dy) if dy else 0  # Yahoo a veces lo da en tanto por uno y a veces en %
    if dy_pct > 3:
        yes.append("Reparte parte de sus beneficios entre sus accionistas (dividendos).")
    if tone == "buenas":
        yes.append("Las noticias de estos días son buenas.")

    # ---- Precaución: riesgos que siguen ahí aunque sea buen momento
    if "Deuda elevada" in flags or (de and de > 250 and r.get("sector") != "Financial Services"):
        no.append("Tiene bastantes deudas: si el negocio va mal o los tipos de interés suben, le cuesta más pagarlas.")
    if "Pierde dinero" in flags or (margin is not None and margin < 0):
        no.append("Ahora mismo pierde dinero: depende de que el negocio mejore.")
    if "trampa" in flags:
        no.append("Es barata, pero quizá por un motivo: el negocio no es de mucha calidad.")
    if vol and vol > 0.45:
        no.append("Su precio sube y baja con mucha fuerza: es de las más arriesgadas. Mejor poco dinero.")
    if tone == "malas":
        no.append("Las noticias de estos días no son buenas.")
    if r.get("market") == "US":
        no.append("Cotiza en dólares: si el dólar baja frente al euro, se gana menos (y al revés).")
    elif r.get("market") == "JP":
        no.append("Cotiza en yenes: los cambios de moneda también influyen en lo que se gana o se pierde.")

    # ---- ¿Por qué ha bajado?
    fall = []
    chg1m, dd = r.get("chg1m") or 0, r.get("drawdown") or 0
    if chg1m < -0.05 or dd < -0.15:
        bad_news = [n for n in news_es if news_tone([n]) == "malas"]
        for n in bad_news[:2]:
            fall.append(f"Según las noticias: «{n['title']}».")
        if bench_chg1m is not None and chg1m < -0.05:
            if bench_chg1m < -0.03:
                fall.append("Toda la bolsa ha bajado este mes" + (" y esta empresa todavía más." if chg1m < bench_chg1m - 0.03 else ", y esta empresa la ha acompañado."))
            elif chg1m < bench_chg1m - 0.08:
                fall.append("La bolsa en general no ha bajado tanto: la caída tiene que ver con la propia empresa o con su sector.")
        if "bajando previsiones" in neg_sig:
            fall.append("Los expertos han rebajado lo que esperan que gane, y eso suele hacer bajar el precio.")
        if chg1m > -0.05 and dd < -0.15:
            fall.append("La mayor parte de la caída fue hace más de un mes; en las últimas semanas está más estable.")
        if not fall:
            fall.append("No hay una noticia clara que lo explique. A veces las acciones bajan porque los inversores venden tras haber subido mucho, o por miedo general en su sector.")

    # ---- ¿Es buen momento? Por qué esperar / qué lo haría mejor / qué está bien ya
    WAIT = [
        ("mínimos de 20 sesiones", "Sigue marcando precios cada vez más bajos.",
         "Cuando pase varios días sin marcar precios más bajos."),
        ("debajo de su media de 20", "Su precio sigue por debajo de su media de las últimas semanas.",
         "Cuando su precio vuelva a superar su media de las últimas semanas."),
        ("MACD sigue empeorando", "El ritmo de caída todavía no se frena.",
         "Cuando el ritmo de caída se frene y empiece a girar."),
        ("todavía bajando", "Las ventas siguen siendo fuertes.",
         "Cuando las ventas pierdan fuerza."),
        ("peor que su índice", "Lo está haciendo peor que el resto de la bolsa.",
         "Cuando deje de hacerlo peor que el resto de la bolsa."),
        ("resultados en", "Presenta sus cuentas en pocos días y el precio puede dar un salto, para arriba o para abajo.",
         "Después de que presente sus cuentas, viendo cómo reacciona el precio."),
        ("bajando previsiones", "Los expertos siguen rebajando lo que esperan que gane.",
         "Cuando los expertos dejen de rebajar sus previsiones."),
    ]
    GOOD = [
        ("sale de sobreventa", "Las ventas fuertes ya han perdido fuerza."),
        ("recuperar su media", "Ha vuelto a superar su precio medio de las últimas semanas."),
        ("por encima de su media", "Se mantiene por encima de su precio medio de las últimas semanas."),
        ("Cruce alcista", "El ritmo de caída se ha frenado y empieza a girar al alza."),
        ("capitulación", "Hubo un día de ventas masivas y después no ha vuelto a bajar: a veces marca el final de una caída."),
        ("mejor que su índice", "Lo está haciendo mejor que el resto de la bolsa."),
        ("subiendo previsiones", "Los expertos esperan ahora que gane más."),
    ]
    neg_list, pos_list = t.get("negative") or [], t.get("positive") or []
    wait = [w for key, w, _ in WAIT if any(key in x for x in neg_list)]
    when_good = [g for key, _, g in WAIT if any(key in x for x in neg_list)]
    good_now = [g for key, g in GOOD if any(key in x for x in pos_list)]
    if "cuchillo" in flags:
        wait.insert(0, "Ha caído muy rápido en el último mes. Comprar mientras cae así es como intentar coger un cuchillo en el aire.")

    # Posible ganancia (sin cifras)
    if up and up >= 0.30 and n_an >= 5:
        gain = "alta"
    elif (up and up >= 0.12) or b.get("valuation", 0) >= 18:
        gain = "media"
    else:
        gain = "baja"

    # Riesgo (sin cifras)
    risk_pts = 0
    risk_pts += 2 if (vol or 0) > 0.45 else 1 if (vol or 0) > 0.30 else 0
    risk_pts += 1 if t.get("label") == "esperar" else 0
    risk_pts += 1 if "cuchillo" in flags else 0
    risk_pts += 2 if (margin is not None and margin < 0) else 0
    risk_pts += 1 if "Deuda elevada" in flags else 0
    risk_pts += 1 if (r.get("drawdown") or 0) < -0.35 else 0
    risk_pts += 1 if tone == "malas" else 0
    risk = "alto" if risk_pts >= 4 or (vol or 0) > 0.45 else "medio" if risk_pts >= 2 else "bajo"

    moment = {"giro": "Buen momento para mirarla con calma",
              "vigilar": "Interesante, pero sin prisa",
              "esperar": "Mejor esperar un poco"}.get(t.get("label"), "Sin señal clara")
    moment_text = {
        "giro": "Hay señales de que la caída se ha frenado. Aun así, conviene entrar poco a poco, no todo de golpe.",
        "vigilar": "Tiene cosas buenas, pero todavía no está claro que haya dejado de bajar. Puede merecer la pena esperar unos días y volver a mirarla.",
        "esperar": "Puede ser una buena empresa, pero ahora mismo sigue bajando. Comprar antes de que se estabilice suele salir caro.",
    }.get(t.get("label"), "")

    tone_text = {
        "buenas": "Lo que se publica estos días sobre la empresa es mayormente positivo.",
        "malas": "Lo que se publica estos días sobre la empresa es mayormente negativo.",
        "mixtas": "Las noticias de estos días tienen de todo: unas buenas y otras malas.",
        "neutras": "Estos días no hay noticias que la muevan mucho.",
    }[tone]

    sector = SECTOR_ES.get(r.get("sector") or "", "")
    return {
        "what": f"Empresa de {sector}." if sector else "",
        "why_yes": yes[:4] or ["Sale entre las mejor valoradas del día según los datos."],
        "why_no": no[:4],
        "caution": no[:5],
        "fall": fall[:3],
        "moment_text": moment_text,
        "wait": wait[:4],
        "when_good": when_good[:3],
        "good_now": good_now[:4],
        "gain": gain,
        "risk": risk,
        "moment": moment,
        "news_tone": tone,
        "news_text": tone_text,
        "news": news_es[:3],
    }


def market(report):
    """Resumen del día en lenguaje sencillo."""
    s = report.get("sentiment") or {}
    macro = {m["id"]: m for m in report.get("macro", [])}
    mk = {m["ticker"]: m for m in report.get("markets", [])}
    lines = []

    v = s.get("value", 50)
    if v < 25:
        lines.append("Mucha gente está con miedo y vendiendo. En estos momentos suelen aparecer gangas, pero hay que tener paciencia.")
    elif v < 45:
        lines.append("El ambiente en la bolsa es de cierta preocupación. Pueden aparecer buenas oportunidades.")
    elif v < 55:
        lines.append("La bolsa está tranquila, sin miedo ni euforia.")
    elif v < 75:
        lines.append("Hay optimismo en la bolsa. Muchas acciones han subido y no están tan baratas.")
    else:
        lines.append("Hay mucha euforia en la bolsa. Cuidado con comprar con prisas: cuando todo el mundo está contento, las cosas suelen estar caras.")

    sp = mk.get("^GSPC")
    if sp and sp.get("chg1m") is not None:
        d = sp["chg1m"]
        lines.append("La bolsa americana ha subido en el último mes." if d > 0.02 else
                     "La bolsa americana ha bajado en el último mes." if d < -0.02 else
                     "La bolsa americana está más o menos igual que hace un mes.")
    ibex = mk.get("^IBEX")
    if ibex and ibex.get("chg1m") is not None:
        d = ibex["chg1m"]
        lines.append("La bolsa española ha subido en el último mes." if d > 0.02 else
                     "La bolsa española ha bajado en el último mes." if d < -0.02 else
                     "La bolsa española está más o menos igual que hace un mes.")

    cpi = macro.get("CPIAUCSL")
    if cpi:
        if cpi["value"] > cpi["prev"] + 0.05:
            lines.append("En Estados Unidos los precios están subiendo más deprisa. Eso puede hacer que los tipos de interés sigan altos, y eso no suele gustar a la bolsa.")
        elif cpi["value"] < cpi["prev"] - 0.05:
            lines.append("En Estados Unidos los precios suben cada vez más despacio. Suele ser una buena noticia para la bolsa.")
        else:
            lines.append("En Estados Unidos los precios siguen subiendo al mismo ritmo que el mes anterior.")
    fed = macro.get("FEDFUNDS")
    if fed:
        if fed["value"] > fed["prev"] + 0.05:
            lines.append("La Reserva Federal (el banco central de EE. UU.) ha subido los tipos de interés: el dinero es más caro y eso frena la bolsa.")
        elif fed["value"] < fed["prev"] - 0.05:
            lines.append("La Reserva Federal (el banco central de EE. UU.) ha bajado los tipos de interés: el dinero es más barato y eso suele ayudar a la bolsa.")
    curve = macro.get("T10Y2Y")
    if curve and curve["value"] < 0:
        lines.append("Hay una señal que a veces avisa de una posible crisis económica (la llamada «curva de tipos invertida»). No es seguro, pero conviene ser prudente.")
    return {"mood": s.get("label", ""), "lines": lines}
