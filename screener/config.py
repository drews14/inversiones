"""Configuración del screener. Cambia aquí pesos, umbrales y fuentes."""

# Prioridad por mercado: multiplica la puntuación al ordenar el ranking global.
MARKET_WEIGHT = {"US": 1.00, "ES": 0.92, "JP": 0.88}
MARKET_LABEL = {"US": "EE. UU.", "ES": "España", "JP": "Japón"}

# Peso de cada bloque (suman 100).
WEIGHTS = {"valuation": 25, "technical": 25, "quality": 25, "analysts": 25}

# Cuántas empresas mostrar.
TOP_GLOBAL = 5
TOP_PER_MARKET = 5
MIN_SCORE = 45            # por debajo de esto no se considera "oportunidad"
MIN_DATA_COVERAGE = 0.6   # fracción mínima de métricas disponibles

# Índices y activos de mercado para el panel macro (ticker Yahoo -> etiqueta)
MARKET_PANEL = {
    "^GSPC": "S&P 500",
    "^NDX": "Nasdaq 100",
    "^DJI": "Dow Jones",
    "^RUT": "Russell 2000",
    "^IBEX": "IBEX 35",
    "^N225": "Nikkei 225",
    "^VIX": "VIX (miedo)",
    "^TNX": "Bono EE. UU. 10a (%)",
    "DX-Y.NYB": "Índice dólar (DXY)",
    "EURUSD=X": "EUR/USD",
    "CL=F": "Petróleo WTI",
    "GC=F": "Oro",
}

# Series macro de la FRED (Reserva Federal de St. Louis), sin API key.
FRED_SERIES = {
    "CPIAUCSL": {"label": "IPC EE. UU. (interanual)", "yoy": True},
    "CPILFESL": {"label": "IPC subyacente EE. UU. (interanual)", "yoy": True},
    "PCEPILFE": {"label": "PCE subyacente (interanual)", "yoy": True},
    "FEDFUNDS": {"label": "Tipos Fed (%)", "yoy": False},
    "UNRATE": {"label": "Paro EE. UU. (%)", "yoy": False},
    "T10Y2Y": {"label": "Curva EE. UU. 10a-2a (pp)", "yoy": False},
    "CP0000EZ19M086NEST": {"label": "IPC zona euro (interanual)", "yoy": True},
    "ECBDFR": {"label": "Tipo depósito BCE (%)", "yoy": False},
    "IRLTLT01ESM156N": {"label": "Bono España 10a (%)", "yoy": False},
    "IRLTLT01DEM156N": {"label": "Bund Alemania 10a (%)", "yoy": False},
}

NEWS_PER_TICKER = 3

# Noticias de mercado (Google News): sección -> (búsqueda, idioma)
MARKET_NEWS = {
    "Wall Street": ("Wall Street stocks S&P 500", "en"),
    "IPC y Fed": ("US CPI inflation Federal Reserve", "en"),
    "España / IBEX": ("IBEX 35 bolsa", "es"),
    "Japón / Nikkei": ("Nikkei 225 stocks", "en"),
}
