# Fuentes de datos y rutina diaria — red abierta (desde 20/11/2026)

**Prevalece sobre `claude/cartera.md` en lo operativo. Léelo en cada informe diario y en cada actualización horaria.**

## Reglas del dueño
- (20/11 16:09) **Todo el análisis se hace UNA vez al día, a las 08:00**. **Las ejecuciones horarias solo actualizan la posición de la cartera** (precios, valor, punto horario, alertas, rango de 52 semanas si se rompe y la alerta del stop de las posiciones vigiladas).
- (20/11 19:43) **No gastar dinero en datos** hasta que el modelo demuestre rentabilidad. Solo fuentes gratuitas que permitan el acceso automático.
- (20/11 20:21) **Vigilar lo que se compre según el modelo** (cartera real y simulador) y avisar cuando toque salir o revisar. Claude nunca compra ni vende en la cuenta real: solo avisa.
- (20/11 20:40) El simulador **no cobra comisiones**.
- (21/11 00:48) **Cartera automática del modelo**: compra sola en cada señal y vende con las salidas del modelo; «Mi simulación» queda para las ideas del dueño. (22/11) **100 € en todas** (también rebotes; solo para ver subidas y bajadas en la misma escala), **sin comisión ni deslizamiento**, y **siempre separadas: «Modelo» (Señal de compra) y «Experimental» (Rebote confirmado)**. Las órdenes anteriores a la ampliación del universo se anularon (22/11 22:58). (23/11 08:52) **Ejecución a la APERTURA** de la primera sesión después del informe que da la señal (primer precio real tras leer el informe; `fetch3.py` guarda `pxo` = apertura del día, `sim_data3.py` la pasa como `o` en simprecios, `cartera_modelo.py` la usa y, si falta, el cierre). Nunca el cierre con el que se calculó la señal.
- (23/11 09:13) **Oportunidades y Riesgo de caída sin cupo de 20 por zona**: se muestran TODAS las que están en zona de compra (Señal de compra, Rebote confirmado) o de salida (Riesgo alto), en una sola lista ordenada por nota; las zonas solo filtran. Las cercanas (Esperar / Riesgo, 60–69) van en `extras`, plegadas (`v3.py`, copia previa `v3_before_lista.py`). Sin límites por zona ni por sector (decisión del dueño 23/11).
- (23/11 10:18) **Universo sin preferentes ni certificados** (Corea: solo códigos acabados en 0; Taiwán: solo 4 cifras; fuera nombres «Pref»). Antes entraban preferentes en lugar de la acción ordinaria (Samsung, Hyundai, LG…). **Acciones de la cartera real fuera del universo**: `universo.py` las añade con `cartera=True`; se descargan y vigilan, pero no salen en Oportunidades/Riesgo, no cuentan en la amplitud del régimen y no dan señales a la cartera del modelo.
- (23/11 10:18) **Histórico del modelo** (Simulador → «Histórico del modelo», `#s-hist`): `python3 /home/claude/bt/historico.py` → `datos/historico.json`. Prueba con el pasado de las reglas de PRECIO de v3.2 sobre los cierres mensuales de Alpha Vantage (EE. UU.; GE excluido), comparada con SPY y con «comprar todas y no tocar». Se recalcula en cada informe de las 08:00 con los valores nuevos.
- (23/11 12:46) **Modelo v3.3** aprobado: fuerza relativa frente a su índice en la Señal de compra y rebote solo con el mercado ya al alza (detalle en mercado-riesgo-caida.md). `bench.py` debe ejecutarse ANTES de `v3.py` (da el `d200` de cada índice).
- (23/11 10:18) **Rentabilidad de Mi cartera**: solo la de su cartera real; nada de reconstruir valores anteriores. Los periodos aparecen cuando hay valor guardado en `historial` en su fecha de inicio.
- (22/11 18:21) «Mi simulación» reiniciada a 10.000 € sin posiciones (referencias `idx0` y `bench0` = cierres del viernes 20/11).
- (22/11 20:32) Mejoras de fiabilidad: índices de referencia por ETF (`bench.py`), posiciones leídas de la base de datos (`ops2cartera.py` → `cartera.json`), copia de seguridad diaria y tarea vigilante.
- (22/11 20:56) **Universo ampliado a ~1.570 empresas** (detalle en mercado-riesgo-caida.md). La descarga tarda ~60 min y **empieza a las 06:30** (tarea propia).
- (22/11 23:07) **Fondos indexados** (no «tus fondos»): apartado de Mercado con los ETF/ETC que sigue la app (rendimiento, frente al MSCI World, rango normal en un mes, riesgo, tendencia, coste, composición y correlaciones). Solo datos, sin señales. **Sin comparación DCA** (el dueño no siempre hace DCA de todos). Se actualiza una vez al día, en el informe de las 08:00.
- (22/11 23:30) **`datos/fondos.json` es visible para todos los usuarios: nada personal dentro.** Lo de cada usuario («Lo que tienes de verdad»: empresas, sectores y países sumando acciones directas y el interior de cada fondo, más el coste anual de sus fondos) se calcula **en su navegador**, dentro de su Mi cartera → Riesgos, con sus propias posiciones.

## Estructura de la app
Cuatro zonas: **Hoy** (portada en una sola vista, primera al abrir), **Mi cartera** (Riesgos incluye «Lo que tienes de verdad»), **Mercado** (Resumen, **Fondos indexados** `#m-fondos`, Oportunidades, Riesgo de caída, Índices y activos, Economía) y **Simulador** (Mi simulación `#s-cuenta`; Cartera del modelo `#s-auto`; Seguimiento del modelo `#s-modelo`; Operaciones simuladas `#s-ops`).

## Datos de mercado grandes = archivos del artefacto
- `datos/oportunidades.json`, `datos/caidas.json`, `datos/simprecios.json`, **`datos/fondos.json`** + índice `datos/mercado.json` = `{actualizado, archivos: [caidas, fondos, oportunidades, simprecios]}`. La app usa, por clave, el más reciente entre archivo y base de datos. **No escribirlos en la base de datos.**
- `datos/senales/<fecha>.json` (uno por día) + índice `datos/senales.json` = `{fechas: [...]}`. Llevan `bench` y `universo`.
- `datos/modelo.json` (cartera del modelo; con `grupos` modelo/experimental).
- `datos/catalogo.json` + `datos/catalogo-{us,es,eu,asia,otros}.json` (buscador del simulador).
- `backup/sistema-tar-gz.b64.txt` + `backup/LEEME.txt`: copia de seguridad de `/home/claude/{op, mk/idx, cat, bt}`.
- Publicación: un solo `publish_files` (slug, `base_version` = versión actual con `get_artifact`, **modo patch**, solo los archivos cambiados, con `as: "datos/<ruta>"` o `"backup/<ruta>"`; rutas de origen bajo /home/claude, no /tmp). Nunca tocar `index.html` en la rutina.
- En la base de datos siguen: `mercado/resumen`, `mercado/indices`, `mercado/macro`, `precios/*`, carteras.

## 06:30 (laborables): descarga de fichas — tarea «Descarga de fichas del modelo 06:30»
Lunes: `python3 universo.py`. Después `nohup python3 fetch3.py <hoy> > /tmp/fetch3_<hoy>.log &` y **esperar en primer plano** (llamadas de Bash de ≤ 9 min con `kill -0 <PID>`) hasta que acabe. Reintentar una vez si falla más del 5 %. Programa la siguiente para el próximo día laborable a las 06:30.

## Orden del informe de las 08:00 (llega a las 07:40; laborables; fines de semana: informe breve sin recalcular mercado ni escribir `historial`/`simhist`)
0. Comprobar que la descarga de las 06:30 terminó (`tail /tmp/fetch3_<hoy>.log`: "ok N fichas"); si sigue, esperar en primer plano; si no se lanzó, lanzarla ahora. Mientras tanto, `python3 bench.py <hoy>` y los pasos 1–4.
1. **Cartera**: `db_list` de `carteras/<uid>/operaciones` → `/tmp/operaciones.json` → `python3 ops2cartera.py /tmp/operaciones.json` (escribe `cartera.json`). Precios con `python3 hora.py '<cierreAnterior>' '<{TICKER:[max52,min52]}>'` (si devuelve `fallos`, completar ese precio). Escribir `precios/*`, `historial`, `horas/<hoy>T07-45`, `informes/<hoy>`. Rango de 52 semanas: `python3 rango52.py`. Los lunes, `cierreAnterior` = cierre del viernes. Después, **`python3 fondos.py <hoy>`** (~20 s) → `datos/fondos.json`.
2. **Índices y activos** (`mercado/indices`) → abajo.
3. **Economía** (`mercado/macro`) → abajo.
4. **Resumen** (`mercado/resumen`), con el termómetro (solo informativo). **Incluir en el texto del informe una frase sobre los fondos indexados** (de `datos/fondos.json`: mejor y peor del día/mes, cuántos sobre su media de 200, novedades como cambios de índice). La app ya muestra en Resumen una tabla de fondos calculada de `fondos.json`.
5. **Modelo v3.2**: `REG_FECHA=<hoy> REG_EXTRA='{"SP500":["<fecha del cierre>",<cierre>],"VIXCLS":[...],"NIKKEI225":[...]}' python3 regimen.py`; noticias en `daily_cfg.json` (`news_o`/`news_r`); `python3 v3.py <hoy>`; copiar `oport_v3.json` y `caidas_v3.json` a `datos/oportunidades.json` y `caidas.json`.
6. **Histórico del modelo**: `python3 /home/claude/bt/historico.py` (publicar `datos/historico.json`). **Simulador**: `python3 sim_data3.py <hoy>` → copiar `simprecios.json` a `datos/simprecios.json`. Después `python3 cartera_modelo.py <hoy>` → `datos/modelo.json`.
7. **Catálogo**: `python3 /home/claude/cat/build.py <hoy>` (~1,5 min).
8. **Punto diario del gráfico del simulador** (si el usuario tiene `simops`): `python3 sim_hist.py <hoy> /tmp/simops.json /tmp/cuenta.json` → set en `carteras/<uid>/simhist/<hoy>`.
9. **Vigilancia** (`python3 vigilancia.py <hoy>`; antes `posiciones.json` con la cartera real de `cartera.json` y las `simops` abiertas). Solo avisos NUEVOS, añadidos al informe como `puntos` tipo "alerta" que empiezan por "Vigilancia" (así los muestra Hoy) y al mensaje del punto 12.
10. **Copia de seguridad**: `cd /home/claude && tar czf backup/sistema.tar.gz --exclude='op/fichas3.json' --exclude='op/*_before_*' --exclude='__pycache__' op mk/idx/*.py mk/idx/*.json cat/*.py bt && base64 -w 0 backup/sistema.tar.gz > backup/sistema-tar-gz.b64.txt && rm backup/sistema.tar.gz`, y actualizar la fecha en `backup/LEEME.txt`.
11. `datos/mercado.json` con `actualizado` de hoy y **un solo** `publish_files` con todos los `datos/*` cambiados y los dos `backup/*`.
12. Mensaje breve al dueño con el enlace de la app: cartera, **avisos de vigilancia (primero)**, simulación, **cartera del modelo** (Modelo y Experimental por separado) y señales del día.
En los `db_write`: leer antes la versión y usar `ifVersion`. Nunca inventar datos: lo que falte, `null`.

## Actualización horaria (solo cartera)
- `python3 /home/claude/op/hora.py '<cierreAnterior por ticker>' '<{TICKER:[max52,min52]}>'`: lee `cartera.json` (si hay una operación nueva durante el día, regenerarlo con `ops2cartera.py`). Escribir `precios/*`, `historial`, `horas`, alertas.
- **Rango de 52 semanas**: si el precio rompe `min52`/`max52`, actualizarlo con `fuente52: "precio de Tradegate HH:MM"`.
- **Posiciones vigiladas**: si una posición real pierde más que su stop por volatilidad por primera vez (`vigilancia_estado.json`, clave `perd10`), avisar al dueño con una línea.

## Vigilante de tareas
- Tarea aparte **«Vigilante de las tareas de Mi cartera»** (11:17 diario, sesión nueva, solo lectura): comprueba el informe de las 08:00, la actualización horaria y el histórico de Alpha Vantage, y avisa si falta alguno. (La descarga de las 06:30, si falta, la lanza y reprograma el informe de las 07:40.)

## Precios de la cartera
- Tradegate **directo con Bash/Python** (no WebFetch): `https://www.tradegatebsx.com/refresh.php?isin=<ISIN>&ts=<epoch>` → `bid` (si no hay, `last`; a veces con coma decimal).

## Fondos indexados (`fondos.py`)
Página de cotización de StockAnalysis de cada ETF/ETC: WTCH → ETR:SPFT · EUNL → ETR:EUNL · IS3N → ETR:IS3N · ASWC → ETR:ASWC · MILL → EPA:MILL · oro PPFB → LON:IGLN (USD) · plata PPFD → LON:ISLN (USD). Datos: cambios 1 sem.–5 años, rentabilidad anualizada 5/10 años, TER, patrimonio, nº de posiciones y serie diaria de 1 año (volatilidad, `rangoMes` = vol/√12, mayor caída, medias de 50/200, correlaciones, `vsMundo1a`/`vsMundoYtd` frente a EUNL). De la página `/holdings/`: `comp` = 25 mayores posiciones (símbolo sin `$`/`@` ni prefijo de bolsa), sectores, países y `cubierto` (% que suman esas 25). Oro y plata: 100 % metal. `comp.fecha` = fecha de la composición. **Sin campos personales.** **MILL (LU2023678449)**: desde el 22/10/2026 es «Amundi Global Sport and eSport» (índice Solactive Sports & eSports; antes MSCI ACWI IMI Millennials). `NOMBRE`/`AVISO` en el script lo muestran en la app. Revisado 23/11: las composiciones de los demás cuadran (EUNL: pesos proporcionales a la capitalización; sectores iguales a los de iShares). Un ISIN nuevo necesita su entrada en el diccionario `SA` del script. Serie propia en `fondos_hist.json`.

## Índices de referencia para MEDIR (`bench.py`)
ETF en moneda local, de StockAnalysis: S&P 500 → SPY · IBEX 35 → BBVAI · Euro Stoxx 50 → EXW1 · Stoxx 600 → EXSA · DAX → EXS1 · CAC 40 → CAC · FTSE MIB → ETFMIB · SMI → CSSMI · FTSE 100 → ISF · Nikkei 225 → 1321 · Taiex → 0050 · Kospi → 069500 · Hang Seng → 2800 · CSI 300 → 510300.

## Índices y activos (`mercado/indices`, lo que se muestra)
- `/home/claude/mk/idx`: `indices.py`, `grupos.json`, `destacados.json`, `base.json`, `hist/`, `manual_<fecha>.json`, `out_<fecha>.json`.
- Manual (`manual_<hoy>.json`): Nasdaq 100, VIX, Euro Stoxx 50, Stoxx 600, DAX, CAC 40, FTSE 100, SMI, FTSE MIB, IBEX 35, Nikkei, Hang Seng, Shanghai, Kospi, Taiex, Bund, bonos España e Italia, prima de riesgo, DXY, Brent, WTI, TTF, oro, plata, cobre. Automático: Tesoro EE. UU., BCE, Coinbase. Si un índice no aparece en la web, se puede mostrar su variación del día desde `bench.json` con la nota "≈ vía ETF".
- Fuentes: AP, Capp Notes "Closing Look", dpa-AFX/Sparkasse y MarketScreener, Valencia Plaza / El Periódico de Ceuta, Rio Times, Newsquawk, Armenpress. Cierres de 2025 en `base.json`.

## Economía (`mercado/macro`)
- `python3 /home/claude/mk/idx/macro.py <hoy>`: FRED, Eurostat, BCE + `manual_macro_<hoy>.json`. FRED rechaza User-Agents personalizados.

## Histórico gratuito (Alpha Vantage, tarea diaria 10:30)
- 25 consultas al día; un asistente en segundo plano guarda date, adjclose desde 2009-12 en `/home/claude/bt/data/<SYM>.csv`. 22/11: 47 valores (EE. UU.). Notas en `bt/NOTAS_DATOS.md` (GE excluido).
- **Reparto (24/11, decidido por Claude a petición del dueño):** 24–25/11, las 25 consultas a histórico (objetivo ~120 valores; con ≥100, `factores.py`). Desde 26/11: 15 histórico + 10 `INSIDER_TRANSACTIONS` de símbolos que ya tengan CSV → `bt/insiders/<SYM>.json`. Con ≥60 símbolos se prueba «compras netas de directivos en 6 meses»; solo se propone si mejora el acierto en las dos épocas.
- **Probar en la descarga del 23/11** 2–3 valores europeos (p. ej. `SAN.MC`, `AIR.PA`, `SAP.DE`, con SYMBOL_SEARCH antes).

## Fuentes gratuitas en uso
- StockAnalysis (User-Agent "cartera-inversiomes/1.0", ~1 consulta por segundo): fichas, ETF, listas por país, bolsa e índice, búsqueda.
- FRED (sin User-Agent propio), BCE, Eurostat, Tesoro de EE. UU., Coinbase, Tradegate, Alpha Vantage gratuito.

## Fuentes que bloquean o prohíben el acceso automático (no forzarlas ni simular un navegador)
- TradingView (condiciones de uso), stooq.com, Yahoo Finance (429), elEconomista, investing.com, CNBC (403), sec.gov (403), FT markets (robots.txt).
