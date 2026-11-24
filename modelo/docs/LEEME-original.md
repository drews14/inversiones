# Mi cartera: modelo de oportunidades y riesgo de caída

Sistema para estudiar la bolsa con datos gratuitos. Cada mañana analiza unas 1.500 empresas de EE. UU., Europa, Japón y Asia y les pone dos notas: **oportunidad** (de 70 en adelante, «Señal de compra») y **riesgo de caída** (de 70 en adelante, «Riesgo alto»). También hay una cartera simulada que compra 100 € en cada señal y vende cuando el modelo da la salida, para medir si acierta. Además lleva un histórico desde 2012 para probar las reglas con el pasado.

**Es una herramienta de estudio, no una recomendación de compra o venta.** Las decisiones son de cada uno.

Este ZIP no incluye datos personales: ni la cartera real, ni operaciones, ni cuentas de bróker.

## Qué hay dentro

| Carpeta | Qué es |
|---|---|
| `app/index.html` | La aplicación (una sola página). |
| `app/datos/` | Los datos de mercado del 24/11/2026: oportunidades, riesgos, fondos indexados, cartera del modelo, señales diarias, histórico y catálogo. |
| `modelo/` | Los programas del modelo, en Python. |
| `mercado/` | El termómetro del mercado, los niveles a vigilar, los índices y la economía. |
| `historico/` | La prueba con el pasado: cierres mensuales de Alpha Vantage de unas 90 acciones de EE. UU. y datos de Kenneth French, más los resultados. |
| `catalogo/` | El buscador de valores del simulador. |
| `docs/` | Cómo funciona el modelo, la rutina diaria y la última revisión. |

## Cómo verlo
- **La app:** se hizo para funcionar como artefacto de Claude (claude.ai), que le da la base de datos y el inicio de sesión. Si abres `app/index.html` en el navegador directamente, la parte de mercado (Oportunidades, Riesgo, Fondos, Histórico) debería cargar desde `app/datos/`. Lo que es de cada usuario (su cartera, su simulación) necesita esa base de datos. Lo más fácil es pedirle a Claude que lo publique como artefacto propio.
- **Los programas:** necesitan Python 3 con `pandas` y `numpy`. Las fuentes son gratuitas: StockAnalysis, FRED, BCE, Eurostat, Alpha Vantage (necesita su propia clave gratuita) y la biblioteca de datos de Kenneth French.

## Orden diario, resumido
Todo está en `docs/fuentes-datos-y-rutina.md`.
1. `modelo/universo.py`, solo los lunes.
2. `modelo/fetch3.py <fecha>`: descarga las fichas de las empresas (~60 min).
3. `modelo/bench.py <fecha>`: índices de referencia.
4. `modelo/regimen.py`: estado de cada mercado (tendencia, pánico, estrés de crédito).
5. `modelo/v3.py <fecha>`: notas y señales.
6. `modelo/sim_data3.py <fecha>` y luego `modelo/cartera_modelo.py <fecha>`: precios del simulador y cartera del modelo.
7. `historico/historico.py`: prueba con el pasado.
8. `mercado/termometro.py` y `mercado/niveles.py`: termómetro y niveles a vigilar.

Algunas rutas dentro de los programas apuntan a la estructura original (`/home/claude/op`, `/home/claude/cartera`, `/home/claude/mk/idx`, `/home/claude/bt`). Si lo montas en otro sitio, hay que ajustarlas.
