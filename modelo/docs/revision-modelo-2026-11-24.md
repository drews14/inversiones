# Revisión integral del modelo — 24/11/2026

**Objetivo:** el modelo no busca explicar mejor el pasado. Busca usar todas las variables disponibles para detectar los mejores puntos de compra y venta. El pasado sirve para probar el modelo y mejorarlo de cara al futuro.

## Mejoras aplicadas el 24/11

### A. Estrés de crédito
- `historico/credito.py` (2012–2026): con los sustitutos Baa y NFCI, el estrés no cambia el acierto porque casi no se activó en ese periodo.
- `historico/regiones.py` (Kenneth French, 1991–2026): en 1991–2011 (2001 y 2008) los meses con estrés fueron los peores en todas las zonas. Rentabilidad media a 6 meses de las ganadoras, sin estrés frente a con estrés:

| Zona | Sin estrés | Con estrés |
|---|---|---|
| EE. UU. | +8,2 % | +0,1 % |
| Europa | +9,3 % | −2,2 % |
| Japón | +3,7 % | −5,0 % |
| Asia-Pacífico | +9,7 % | +2,9 % |

- **Regla en `modelo/regimen.py`:** hay estrés si el NFCI es ≥ 0 o si el diferencial Baa–10 años (BAA10Y) sube más de 0,5 puntos en 3 meses.
- El high yield queda solo como aviso, porque FRED solo publica 3 años y no se puede probar.

### B. Datos antiguos
- Para dar señal, la ficha de la empresa debe tener 5 días como máximo.
- Con más de 21 días (cotización congelada), la empresa queda descartada.

### C. Acierto absoluto
- Acierto a 6 meses en absoluto (la acción sube), con señal frente a sin señal:
  - 2012–19: 71,7 % frente a 71,8 %.
  - 2020–26: 68,7 % frente a 68,4 %.
- Acierto a 6 meses frente al S&P 500 (la acción lo bate), con señal frente a sin señal:
  - 2012–19: 58,1 % frente a 55,9 %.
  - 2020–26: 52,6 % frente a 51,4 %.
- La ventaja del modelo es relativa: bate al índice más a menudo, pero no gana más a menudo en absoluto.

### D. Salidas (`historico/salidas.py`)
- Se probaron seis reglas de salida. Se juzgan por la rentabilidad anual y la caída máxima de la cartera.
- La salida actual es la mejor en las dos épocas:
  - 2012–19: 22,2 % al año, con caída máxima de −11,7 %.
  - 2020–26: 25,6 % al año, con caída máxima de −18,6 %.

### E. Fuera de EE. UU.
Porcentaje de veces que las empresas que vienen subiendo baten a su mercado en los 6 meses siguientes:

| Zona | 1991–2011 | 2012–2019 | 2020–2026 |
|---|---|---|---|
| Europa | 72 % | 67 % | 64 % |
| EE. UU. | 63 % | 56 % | 55 % |
| Japón | 51 % | 53 % | 53 % |
| Asia-Pacífico | 62 % | 51 % | 43 % |

### F. Seguimiento en vivo
- Se cuentan las señales independientes: las del mismo día y sector valen como una sola prueba.
- Cada acierto se muestra con su margen de error, al 95 %.

## Debilidades abiertas
1. La ventaja medida es pequeña y solo relativa. Además hay sesgo de supervivencia: el histórico solo incluye grandes empresas de EE. UU. que existen hoy.
2. Calidad, valor, analistas y flujo no se validan con nuestras propias señales; solo con estudios de factores públicos.
3. El histórico usa datos mensuales y el modelo funciona con datos diarios.
4. El experimental (rebotes) es débil.
