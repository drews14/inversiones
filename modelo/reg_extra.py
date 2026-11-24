"""Último cierre del S&P 500, VIX y Nikkei 225 (Yahoo) para regimen.py: FRED los publica con un día de retraso.
Sustituye al REG_EXTRA que antes se escribía a mano. Imprime {"SP500": ["AAAA-MM-DD", cierre], ...}."""
import json
try:
    import yfinance as yf
    out = {}
    for fred, y in (("SP500", "^GSPC"), ("VIXCLS", "^VIX"), ("NIKKEI225", "^N225")):
        try:
            h = yf.Ticker(y).history(period="10d", interval="1d", auto_adjust=False)["Close"].dropna()
            if len(h): out[fred] = [h.index[-1].strftime("%Y-%m-%d"), round(float(h.iloc[-1]), 2)]
        except Exception:
            pass
    print(json.dumps(out))
except Exception:
    print("{}")
