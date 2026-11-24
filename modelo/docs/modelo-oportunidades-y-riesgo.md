# Mercado → Oportunidades y Riesgo de caída — modelo v3.2 (universo ampliado el 22/11/2026)

Complementa `claude/cartera.md` y `claude/fuentes-datos.md` (rutina). **v3 desde el 20/11 20:05; v3.1 desde las 21:40; listas por zona desde las 22:30; v3.2 desde las 23:55; universo de ~1.570 valores desde el 22/11 22:00; listas sin cupo desde el 23/11.** Scripts en `/home/claude/op`: `universo.py`, `fetch3.py`, `regimen.py`, `v3.py`, `sim_data3.py`, `vigilancia.py`, `sim_hist.py`, `cartera_modelo.py`, `bench.py`, `ops2cartera.py`, `hora.py`, `fondos.py` (copias previas: `*_before_*.py`; universos anteriores en `universo_375.json` y `universo_1570.json`). Salida: `datos/oportunidades.json`, `datos/caidas.json`, `datos/simprecios.json`, `datos/senales/<fecha>.json`, `datos/modelo.json`. Estado local: `regimen_estado.json`, `vigilancia_estado.json`, `modelo_estado.json`.

Pedidos del dueño: "mayor exactitud"; "depurar muy bien"; "si algo está a 90 será compra"; "todas las mejoras sin gastar dinero"; "simplificar, lógica en desplegable"; "tener en cuenta el recorrido"; "avisar al salir"; "aguantar una bajada para coger la subida" (rebote); "corrige todo lo que veas" (v3.1); "analiza el modelo contrastando con otras fuentes" y "aplica cambios" (v3.2); (22/11) "analizar al completo S&P 500, Nasdaq, IBEX 35, Euro Stoxx, Nikkei, CSI 300, Taiwán y Corea" manteniendo el resto de Europa y Hong Kong, Taiwán 150 y Corea 200; (23/11) mostrar solo zona de compra o salida, sin cupo por zona ni límite por sector; separar Modelo y Experimental. TradingView descartado (prohíbe la extracción automática).

## Cómo se mejora el modelo (pedido del dueño 23/11 14:16: «que prediga mejor, no que tenga mejor %»)
- **Criterio único: el ACIERTO** (% que bate a su índice después de la señal frente a las que no tienen señal), no la rentabilidad.
- Un cambio solo se propone si **sube el acierto en las dos épocas** del histórico (2012-2019 y 2020-2026) y luego se confirma en real.
- **Histórico** (`bt/historico.py` → `prediccion` en historico.json; página «¿Acierta? Lo que importa»): acierto a 3, 6 y 12 meses con y sin señal, y por condición (ayuda / resta / dudosa). 23/11, a 6 meses: con señal 58 % y 53 % frente a 56 % y 51 % sin señal. Condiciones: giro, mercado y fuerza relativa **ayudan**; impulso de 12 meses **dudosa** (+0,8 y −5,2 puntos): candidata a perder peso si se confirma con más empresas.
- **Real** (Seguimiento → «¿Qué parte de la nota acierta?»): desde el 24/11 cada `senales/<fecha>.json` guarda en `todas` los bloques de la nota (`bq`: tendencia, momento, calidad, valor, analistas, flujo) y las condiciones que fallan (`cf`). Con ≥ 30 casos y 20 días se ve qué bloque ayuda (alto ≥ 70 frente a bajo < 40) → ajustar pesos.

## ¿Rebote o tendencia? (23/11 16:00, `bt/rebote_vs_tendencia.py` → `bt/rebote_vs_tendencia.json`)
Episodios de caída ≥ 25 % desde el máximo de 12 meses (66 empresas de EE. UU., mensual). Entrada → compra sobre el mínimo (mediana) · acierto a 12 meses frente al S&P · falsas alarmas (mínimo nuevo después):
- Primer rebote sin mirar el mercado: +12 % · 63 % · 44 %.
- **Rebote con el mercado al alza (experimental actual)**: +18 % · 65 % · 34 %.
- Rebote y sobre su media de 10 meses: +28 % · 63 % · 20 %.
- **Señal de compra del modelo**: +33 % · **75 %** (71 % en 2012-19, 81 % desde 2020) · 20 %.
Conclusión: comprar antes es más barato pero acierta menos y da muchas más falsas alarmas (y el sesgo de supervivencia favorece a las entradas tempranas). Se mantiene la estructura: Modelo = tendencia confirmada; Experimental = rebote con el mercado al alza, medido aparte.
**Relleno de precios diarios** (`serie_relleno.py` → `serie_hist.json`, 888 valores ≥ 20 % bajo su máximo + cartera): el giro del rebote (media de 10 sesiones y mínimo creciente) funciona desde el 23/11 sin esperar al archivo propio; v3.py une serie_hist con el archivo diario. Desde ~4/12 el archivo propio ya basta.

## v3.4 — datos gratuitos nuevos (aprobado por el dueño 23/11 14:55)
1. **Revisiones de analistas** (v3.py): previsión de BPA del próximo año = precio / PER estimado de la ficha; revisión = cambio % frente al archivo de hace ~30 días (mientras no exista, 14-27 días; `OLD_DIAS`). También cambio del precio objetivo. Con revisiones, pesan la mitad del bloque Analistas (BPA 1,2 · objetivo 0,8). Se activan hacia el 4/12 (14 días) y del todo hacia el 18/12. Se guardan en cada ítem (`revisiones`) y en `senales.todas` (`rv`) para medir en real si predicen (Seguimiento → «¿Qué parte de la nota acierta?», fila «Revisiones»).
2. **Pesos por zona** según factores públicos (`bt/factores.py` → `bt/factores.json` y `datos/factores.json`; Kenneth French por región + AQR QMJ): EE. UU. tendencia 20 · momento 25 · calidad 20 · valor 10 · analistas 15 · flujo 10; Europa/España 20·25·20·20·10·5; Japón 20·10·15·35·15·5; Asia sin Japón 15·25·20·25·10·5. Sin revisiones todavía, analistas a la mitad. Con esto, el 23/11 entran Allianz y Bayer (15 señales de compra).
3. Copias previas: `v3_before_rev.py`. Fuentes descargadas en `bt/factores/` (French CSV y AQR xlsx).

## v3.3 — cambios aprobados por el dueño tras la prueba con el pasado (23/11 12:46)
1. **Fuerza relativa** en la Señal de compra (condición `fuerza`, tope 64): la empresa tiene que estar más por encima de su media de 200 que su índice de la suya. Índice por país (`BENCH_PAIS` en v3.py; resto de Europa → Stoxx 600); `d200` de cada índice en `bench.json` (calculado por `bench.py` con la serie diaria de 1 año del ETF; S&P 500 y Nikkei con respaldo de FRED vía regimen.json). Sin dato del índice, la condición no se aplica. En el histórico (variante «d200 rel»): mejor en 2012-2019 y en 2020-2026.
2. **Rebote solo con el mercado ya al alza** (condición `mercadoalza` = `tendencia` de su zona en regimen.json; sustituye a `caidamercado`). La regla anterior falló en los dos periodos del histórico.
3. Las órdenes del 23/11 (señales de las 08:00 con v3.2) se mantienen; las reglas nuevas cuentan desde el informe del 24/11. Copia previa: `v3_before_fuerza.py`, `bench_before_d200.py`, `bt/historico_before_fuerza.py`.
4. Histórico con las reglas nuevas (cada cartera por separado): modelo **+23,7 %/año, caída −18,6 %** (sin tocar +23,3 %, −24,7 %); experimental +40,4 %, −32,6 %, **no fiable por sesgo de supervivencia** (aviso en la app).

## v3.2 — cambios tras contrastar con la investigación (20/11 23:55)
1. **Recorrido fuera del orden**: las listas se ordenan por estado, nota y atractivo; el recorrido (precio objetivo) solo se muestra (los precios objetivo predicen poco). Las revisiones de previsiones entran con 30 días de archivo.
2. **Rebote solo con caída de todo su mercado** (`caidamercado`: zona con < 50 % de valores sobre su MA200 o índice ≤ −5 % bajo su MA200; si falla, nota máx. 64).
3. **Stop por volatilidad** (`stop`, `st` en simprecios) = 0,25 × amplitud de 52 sem., entre 8 y 25 %.
4. **Régimen con confirmación de 3 días** (`regimen_estado.json`; `REG_EXTRA` para el último cierre que FRED aún no publica).
5. **Baja volatilidad dentro de calidad** (percentil inverso de amp52).
Descartado por la evidencia: deriva tras resultados y más reglas a mano. Criterio de éxito fijado de antemano: 70+ bate a su índice y a los tramos bajos a 20 y 60 días con ≥ 30 casos; si no en 3 meses, se simplifica.

## Escala
- Oportunidades: **70+ = compra** (85+ fuerte) · 60–69 esperar · 50–59 vigilar · < 50 sin señal · filtros → Descartada. Dos compras: **«Señal de compra»** y **«Rebote confirmado»** (experimental).
- Riesgo de caída: **70+ = venta o salida** · 60–69 riesgo · 50–59 vigilar.

## Universo, zonas, datos y archivo
**~1.570 valores** por regla fija (universo.py, lunes): **EE. UU. 515** (S&P 500 + Nasdaq 100 completos) · **España 35** (≈ IBEX 35) · **Europa 120** (50 mayores de la eurozona ≈ Euro Stoxx 50, más resto hasta 120) · **Japón 225** · **China 300** (≈ CSI 300) · **Taiwán 150** · **Corea 200** (≈ KOSPI 200) · **Hong Kong 25**. Fuera de EE. UU. los índices se aproximan con las mayores por capitalización. **(23/11) Sin preferentes ni certificados** (Corea: solo códigos acabados en 0; Taiwán: 4 cifras; fuera nombres «Pref»): antes entraban preferentes en lugar de Samsung, Hyundai, LG, SK… **Acciones de la cartera real fuera del universo**: `cartera=True`, se descargan y vigilan, pero no salen en las listas, no cuentan en la amplitud del régimen y no dan señales a la cartera del modelo. Fichas de StockAnalysis (fetch3.py, ~60 min, tarea de las 06:30; guarda también `pxo` = apertura del día) y archivo diario `archivo/<fecha>.json.gz`. 23/11: 1.498 fichas, 72 fallos.

## Listas
(23/11) **Todas las que están en zona de compra** (Señal de compra, Rebote confirmado) **o de salida** (Riesgo alto), en una sola lista ordenada por nota; las zonas solo filtran; las cercanas (60–69) aparte, plegadas (`extras`). **Sin límite por zona ni por sector** (decisión del dueño). Aviso de concentración si más de 3 del mismo sector en una zona.

## Atractivo = bloques en percentil del universo
Tendencia 20 · Momento 20 · Calidad 20 (GPA, ROIC, Piotroski, deuda, baja volatilidad) · Valor frente a su sector 20 · Analistas 5 (10 con revisiones) · Flujo 10 en EE. UU., 5 fuera.

## Señal de compra — condiciones y topes
tendencia → 49 · valoración fiable → 59 · giro (precio ≥ MA50) → 64 · datos ≤ 7 días → 64 · noticias → 64 · resultados en ≤ 7 días → 64 · mercado favorable en su zona → 69 · atractivo ≥ 70 sin filtros → 69. Filtros: ROIC y ROE < 5 %; deuda/patrimonio ≥ 3; ficha > 35 días. **Histéresis**: con nota ≥ 70 ayer y 60–69 hoy con tendencia sana, mantiene «Señal de compra».

## «Rebote confirmado» (experimental)
Elegibles: caída ≥ 25 % desde el máximo de 52 semanas, sin filtros, calidad y valor ≥ 55 y media ≥ 70. Nota = 40 % calidad + 40 % valor + 20 % analistas, con topes por giro, caída de su mercado, pánico/estrés, valoración, datos, noticias y resultados → 64. Salida: nuevo mínimo de 52 semanas o su stop.

## Riesgo de caída
Base = 25 % (100 − tendencia) + 25 % (100 − momento) + 15 % calidad + 15 % valor + 10 % analistas + 10 % flujo (invertidos). Sin tendencia bajista → máx. 59; precio sobre MA50 → máx. 64; mercado desfavorable +5.

## Régimen de mercado (regimen.py)
Por zona (EE. UU., España, Europa, Japón, Asia): índice sobre MA200 (S&P 500 y Nikkei, FRED) o amplitud MA200 ≥ 50 %; sin estrés (NFCI < 0, high yield < 5 % sin subir > 1 punto en 3 meses); sin pánico (VIX < 30 o amplitud MA50 ≥ 40 %). Cambio confirmado con 3 días.

## Vigilancia, simulador y cartera del modelo
- Vigilancia: SALIR (riesgo ≥ 70, tendencia rota; en rebotes, mínimo de 52 sem. o stop) · REVISAR (nota < 50, pérdida > stop, 3 meses, mínimo de 52 sem.) · AVISO (zona a desfavorable). Solo avisos nuevos.
- «Mi simulación» (ideas del dueño): sin comisión; reiniciada a 10.000 € el 22/11.
- **Cartera del modelo** (`cartera_modelo.py`): 100 € por señal (también rebotes), **a la apertura de la sesión siguiente** al informe que da la señal (23/11; si falta la apertura, al cierre), **sin comisión ni deslizamiento**; una sola compra por valor mientras está en cartera o pendiente; vende con las salidas del modelo. **Desde el 23/11, Modelo y Experimental en páginas separadas** del Simulador («Cartera del modelo» y «Cartera experimental»; `hist[].g` guarda cada grupo).

## Medición con datos (Seguimiento del modelo, automático)
`datos/senales/<fecha>.json`: `op`, `ri`, `todas`, `bench`, `modelo`, `universo`. Cada empresa cuenta una sola vez, desde su primera señal. Veredicto (≥ 20 días y ≥ 30 compras) **solo con «Señal de compra»** (23/11); casillas separadas para Modelo, Experimental, En espera y Avisos de caída.

## Histórico gratuito y prueba con el pasado
Alpha Vantage (25 series mensuales/día, tarea de las 10:30). 23/11: 70 archivos (68 de EE. UU., SAP.DEX correcto, 0HLE.LON descartado: precios congelados). Notas en `bt/NOTAS_DATOS.md` (GE excluido; ASML desde 2013; BRK.B desde 2010-02).
**Histórico del modelo** (`bt/historico.py` → `datos/historico.json`, página del Simulador): reglas de PRECIO de v3.2 en datos mensuales desde 2012, 66 empresas de EE. UU.: modelo **+22,8 %/año, caída máx. −18 %**; mismas empresas sin tocar +23,3 %, −25 %; S&P 500 +14,3 %, −24 %. Experimental +4,4 %/año, caída −56 %. 37 % de las operaciones baten al S&P 500; mediana −4,2 puntos: el resultado lo hacen pocas operaciones muy buenas.

### Variantes probadas (23/11, `bt/variantes.py`; ajuste 2012-2019 / validación 2020-2026; NO aplicadas sin permiso del dueño)
- Casi todas las variantes de precio quedan entre +21 % y +24 % al año: con 66 grandes empresas, las reglas de precio apenas distinguen.
- **Fuerza relativa** (solo comprar si bate al S&P 500 en 6 meses): +23,5 %/año y −17 % de caída; mejora pequeña pero en los dos periodos → candidata.
- Salida «solo bajo la media de 10 meses» = mismo resultado que la actual (más simple).
- Salidas por caída desde el máximo (−20 %, −25 %): peor (≈ +21 %). Nada de objetivos de beneficio ni stops ajustados.
- Filtro de baja volatilidad: peor (+19 %). Concentrar en las 15 de más impulso: +26 % pero caída −29 %.
- Filtro de mercado: casi no cambia la rentabilidad; reduce algo la caída.
- **Rebote**: la regla actual (comprar con el mercado cayendo) falla en los dos periodos (+8,5 %/año, −60 %). Comprar el rebote con el mercado ya al alza sale muy bien (+35 %), pero depende de NFLX, TSLA, PLTR y NVDA: sesgo de supervivencia fuerte, no fiable.

## Resultados
- 20/11 (v3.2, 375 valores): 9 señales de compra.
- 21/11 recalculado con ~1.520 valores: 14 señales de compra y 1 rebote.
- 23/11: 13 señales de compra y 2 rebotes (PDD, China Pacific Insurance); 234 en riesgo alto (182 de Asia). Mercado: EE. UU., Japón y Asia desfavorables; España y Europa favorables. 16 órdenes de la cartera del modelo a la apertura del 23/11.
