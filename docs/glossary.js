"use strict";
// Explicaciones sencillas de cada concepto (botones ⓘ).
const GLOSS = {
  score: ["Nota de 0 a 100", "Resume en un número lo atractiva que parece la empresa hoy según cuatro bloques: si está barata, si ha caído mucho, si es un buen negocio y qué opinan los analistas. No es una garantía: es una forma de ordenar qué mirar primero."],
  valuation: ["Valoración", "Mide si la acción está barata comparada con lo que gana la empresa y con empresas parecidas de su sector. Usa el PER, el PEG y el flujo de caja libre."],
  technical: ["Sobreventa técnica", "Mide cuánto ha caído el precio recientemente. Una caída fuerte puede ser una oportunidad… o una señal de problemas, por eso se combina con los demás bloques."],
  quality: ["Calidad / fiabilidad", "Mide si es un buen negocio: si gana dinero con su capital (ROE), si tiene poca deuda, si tiene buenos márgenes y si sus beneficios crecen. Sirve para evitar empresas baratas que están baratas por algo."],
  analysts: ["Consenso de analistas", "Lo que opinan los analistas profesionales que siguen la empresa: cuánto creen que puede subir hasta su precio objetivo y si recomiendan comprar o vender. Se equivocan a menudo, pero da una idea del sentimiento profesional."],
  pe: ["PER (precio / beneficio)", "Cuántos años de beneficios actuales pagas al comprar la acción. Un PER de 10 significa que pagas 10 veces lo que gana al año. Más bajo = más barata, pero hay que compararlo con empresas del mismo sector."],
  peg: ["PEG", "Es el PER dividido por el crecimiento de beneficios. Por debajo de 1 se suele considerar que pagas poco por el crecimiento que tiene la empresa."],
  roe: ["ROE (rentabilidad sobre el capital)", "Cuánto beneficio genera la empresa por cada euro que han puesto sus accionistas. Por encima del 15–20 % se considera un negocio de calidad."],
  rsi: ["RSI 14", "Indicador de 0 a 100 que mide la fuerza de las subidas y bajadas de las últimas 14 sesiones. Por debajo de 30 se dice que está «sobrevendida» (ha caído mucho y rápido); por encima de 70, «sobrecomprada»."],
  sma200: ["Distancia a la media de 200 sesiones (MM200)", "La media del precio de los últimos ~10 meses. Si el precio está muy por debajo, la acción está en tendencia bajista o en una caída fuerte; muy por encima, en tendencia alcista."],
  drawdown: ["Caída desde máximos de 52 semanas", "Cuánto ha bajado el precio desde su máximo del último año."],
  upside: ["Potencial", "Diferencia entre el precio actual y el precio objetivo medio de los analistas. Es una estimación, no una promesa."],
  analysts_n: ["Número de analistas", "Cuántos analistas profesionales siguen la empresa. Con menos de 5 la opinión es poco representativa."],
  consensus: ["Consenso", "La recomendación media de los analistas: desde «compra fuerte» hasta «vender»."],
  timing: ["Momento de entrada", "Indica si la caída parece estar frenando. «Señal de giro»: hay indicios de recuperación. «Vigilar»: señales mixtas. «Esperar»: sigue cayendo. Se basa en RSI, medias, MACD, volumen, comparación con su índice, resultados próximos y revisiones de los analistas."],
  macd: ["MACD", "Indicador que compara dos medias del precio (rápida y lenta). Cuando la rápida cruza hacia arriba a la lenta («cruce alcista») suele indicar que la tendencia empieza a mejorar."],
  target: ["Precio objetivo", "El precio al que los analistas creen que llegará la acción en unos 12 meses. Se muestra la media y el rango entre el analista más pesimista y el más optimista. Es una estimación y a menudo se equivocan."],
  risk: ["Riesgo de caída", "Puntuación de 0 a 100 que suma señales de que una acción que iba bien empieza a caer: perder sus medias de 50 o 200 sesiones (+20 cada una si acaba de ocurrir), cruce bajista del MACD (+15), caída desde su máximo reciente (hasta +15), pérdida rápida de fuerza en el RSI (+10), hacerlo peor que su índice (+10) y ventas con mucho volumen (+10). Desde 35 aparece en la lista; desde 55 es «alerta alta»."],
  stoploss: ["Orden stop-loss", "Una orden que se deja puesta en el bróker para vender automáticamente si el precio baja hasta un nivel que tú eliges. Sirve para limitar pérdidas sin tener que estar pendiente. Si el precio cae de golpe, puede venderse algo por debajo de ese nivel."],
  isin: ["ISIN", "Código internacional que identifica una acción concreta (12 caracteres, por ejemplo US0378331005 para Apple). Sirve para buscarla sin errores en cualquier bróker."],
  sentiment: ["Termómetro del mercado", "Mide el ánimo general de la bolsa de 0 (pánico) a 100 (euforia). Se calcula con el porcentaje de empresas del S&P 500 por encima de sus medias de 50 y 200 sesiones y con el VIX. Con miedo suele haber más oportunidades; con euforia, más riesgo de comprar caro."],
  "^GSPC": ["S&P 500", "Índice de las 500 mayores empresas de EE. UU. Es la referencia principal de la bolsa mundial."],
  "^NDX": ["Nasdaq 100", "Las 100 mayores empresas no financieras del Nasdaq, sobre todo tecnológicas (Apple, Microsoft, NVIDIA…)."],
  "^DJI": ["Dow Jones", "Índice histórico de 30 grandes empresas de EE. UU."],
  "^RUT": ["Russell 2000", "Índice de 2.000 empresas pequeñas de EE. UU. Refleja cómo va la economía «de a pie» americana."],
  "^IBEX": ["IBEX 35", "Las 35 empresas más negociadas de la bolsa española (Santander, Inditex, Iberdrola…)."],
  "^N225": ["Nikkei 225", "El principal índice de la bolsa de Japón, con 225 grandes empresas (Toyota, Sony…)."],
  "^VIX": ["VIX (índice del miedo)", "Mide cuánto esperan los inversores que se mueva la bolsa americana en el próximo mes. Por debajo de 15: calma. Por encima de 25–30: miedo o pánico."],
  "^TNX": ["Bono EE. UU. a 10 años", "El interés que paga el Gobierno de EE. UU. por prestarle dinero a 10 años. Si sube, las acciones suelen sufrir porque los bonos se vuelven más atractivos y endeudarse sale más caro."],
  "DX-Y.NYB": ["Índice dólar (DXY)", "Mide la fuerza del dólar frente a otras monedas principales. Un dólar fuerte hace que las acciones americanas valgan menos en euros."],
  "EURUSD=X": ["EUR/USD", "Cuántos dólares vale un euro. Si sube, tus acciones americanas valen algo menos en euros (y al revés)."],
  "CL=F": ["Petróleo WTI", "Precio del barril de petróleo de referencia en EE. UU. Afecta a la inflación y a empresas de energía, aerolíneas, transporte…"],
  "GC=F": ["Oro", "Precio de la onza de oro. Suele subir cuando hay miedo o inflación."],
  CPIAUCSL: ["IPC de EE. UU.", "Cuánto han subido los precios en EE. UU. en el último año (inflación). La Reserva Federal intenta que esté cerca del 2 %. Si sube, es probable que los tipos de interés sigan altos."],
  CPILFESL: ["IPC subyacente", "La inflación sin energía ni alimentos frescos, que son muy volátiles. Muestra mejor la tendencia de fondo de los precios."],
  PCEPILFE: ["PCE subyacente", "Otra medida de inflación: es la que más mira la Reserva Federal para decidir los tipos de interés."],
  FEDFUNDS: ["Tipos de la Fed", "El tipo de interés que marca la Reserva Federal (el banco central de EE. UU.). Tipos altos encarecen el dinero y frenan la bolsa; bajadas de tipos suelen impulsarla."],
  UNRATE: ["Paro en EE. UU.", "Porcentaje de personas sin empleo que buscan trabajo. Si sube mucho y rápido, puede anunciar una recesión."],
  T10Y2Y: ["Curva de tipos 10a - 2a", "Diferencia entre el interés del bono a 10 años y el de 2 años. Normalmente es positiva. Si se vuelve negativa («curva invertida»), históricamente ha avisado de recesiones."],
  CP0000EZ19M086NEST: ["IPC de la zona euro", "La inflación de los países del euro. El BCE intenta que esté cerca del 2 %."],
  ECBDFR: ["Tipo de depósito del BCE", "El tipo de interés principal del Banco Central Europeo. Afecta a hipotecas, préstamos y a la bolsa europea."],
  IRLTLT01ESM156N: ["Bono español a 10 años", "El interés que paga España por endeudarse a 10 años."],
  IRLTLT01DEM156N: ["Bund alemán a 10 años", "El interés que paga Alemania a 10 años. Se usa como referencia «segura» en Europa."],
  SPREAD_ES: ["Prima de riesgo", "Diferencia entre el interés del bono español y el alemán (en puntos básicos; 100 pb = 1 %). Cuanto más alta, más desconfianza hay en la economía española."],
};

function infoBtn(key) {
  return GLOSS[key] ? `<button class="info" data-g="${key}" aria-label="Qué es ${GLOSS[key][0]}">i</button>` : "";
}

function showGloss(key) {
  const g = GLOSS[key];
  if (!g) return;
  document.querySelector("#gloss-title").textContent = g[0];
  document.querySelector("#gloss-text").textContent = g[1];
  document.querySelector("#gloss").hidden = false;
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-g]");
  if (b) {
    e.preventDefault();
    e.stopPropagation();
    showGloss(b.dataset.g);
    return;
  }
  if (e.target.id === "gloss" || e.target.id === "gloss-ok") document.querySelector("#gloss").hidden = true;
}, true);
