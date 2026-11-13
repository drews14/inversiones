"""Servidor de la app: sirve la web (docs/) y la API del simulador con precios al momento.

Arrancar:  python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
"""
import asyncio
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, portfolio, prices

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Oportunidades", docs_url=None, redoc_url=None, openapi_url=None)
COOKIE = "sid"


@app.on_event("startup")
def _startup():
    db.init()
    prices.start()
    # al arrancar, sigue los valores que hay en todas las carteras
    with db.conn() as c:
        prices.track([r["ticker"] for r in c.execute("SELECT DISTINCT ticker FROM trades")])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- autenticación
_attempts = defaultdict(deque)  # ip -> intentos de login recientes


def _limit(request: Request, max_n=10, window=600):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    q = _attempts[ip]
    now = time.time()
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= max_n:
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")
    q.append(now)


def current_user(request: Request):
    u = db.user_from_token(request.cookies.get(COOKIE))
    if not u:
        raise HTTPException(401, "Inicia sesión")
    return u


def _set_cookie(request: Request, resp: Response, token: str):
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(COOKIE, token, max_age=db.SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=secure)


class Login(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=200)


class Register(Login):
    invite: str = Field(min_length=4, max_length=20)


@app.get("/api/health")
def health():
    return {"ok": True, "server": True}


@app.post("/api/login")
def api_login(body: Login, request: Request, response: Response):
    _limit(request)
    token = db.login(body.username, body.password)
    if not token:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    _set_cookie(request, response, token)
    return {"ok": True}


@app.post("/api/register")
def api_register(body: Register, request: Request, response: Response):
    _limit(request)
    try:
        uid = db.use_invite(body.invite, body.username, body.password)
    except Exception:
        raise HTTPException(400, "Ese nombre de usuario ya existe")
    if not uid:
        raise HTTPException(400, "Código de invitación no válido o ya usado")
    _set_cookie(request, response, db.login(body.username, body.password))
    return {"ok": True}


@app.post("/api/logout")
def api_logout(request: Request, response: Response):
    db.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(u=Depends(current_user)):
    return {"username": u["username"], "is_admin": bool(u["is_admin"])}


@app.post("/api/invites")
def make_invite(u=Depends(current_user)):
    if not u["is_admin"]:
        raise HTTPException(403, "Solo el administrador puede invitar")
    return {"code": db.new_invite(u["id"])}


# ---------------------------------------------------------------- precios
@app.get("/api/search")
def search(q: str, u=Depends(current_user)):
    if len(q.strip()) < 2:
        return []
    return prices.search(q.strip())


@app.get("/api/quote/{ticker}")
def quote(ticker: str, u=Depends(current_user)):
    q = prices.get(ticker.upper())
    if not q:
        raise HTTPException(404, "No encuentro ese valor")
    return q


@app.get("/api/history/{ticker}")
def history(ticker: str, range: str = "1mo", u=Depends(current_user)):
    if range not in prices.RANGES:
        raise HTTPException(400, "Rango no válido")
    pts = prices.series(ticker.upper(), range)
    if not pts:
        raise HTTPException(404, "Sin datos para ese valor")
    return {"ticker": ticker.upper(), "range": range, "points": pts}


@app.get("/api/stream")
async def stream(request: Request, tickers: str = "", u=Depends(current_user)):
    """Envía precios cada pocos segundos (Server-Sent Events) para los valores de tus carteras y los que mires."""
    extra = [t for t in tickers.upper().split(",") if t][:30]

    async def gen():
        while not await request.is_disconnected():
            held = {p["ticker"] for a in portfolio.accounts_for(u["id"], live=False) for p in a["positions"]}
            ts = sorted(held | set(extra))
            prices.track(ts)
            yield f"data: {json.dumps(prices.snapshot(ts), default=str)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- carteras y operaciones
class NewAccount(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    kind: str = Field(pattern="^(sim|real)$")
    start_cash: float = Field(default=10000, ge=0, le=10_000_000)
    fee_eur: float = Field(default=1.0, ge=0, le=100)


class NewTrade(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    side: str = Field(pattern="^(buy|sell)$")
    qty: Optional[float] = Field(default=None, gt=0)
    amount_eur: Optional[float] = Field(default=None, gt=0)
    price: Optional[float] = Field(default=None, gt=0)   # solo carteras reales
    date: Optional[str] = None                           # solo carteras reales, AAAA-MM-DD
    note: Optional[str] = Field(default=None, max_length=200)


@app.get("/api/accounts")
def list_accounts(u=Depends(current_user)):
    return portfolio.accounts_for(u["id"])


@app.post("/api/accounts")
def create_account(body: NewAccount, u=Depends(current_user)):
    with db.conn() as c:
        n = c.execute("SELECT COUNT(*) FROM accounts WHERE user_id = ?", (u["id"],)).fetchone()[0]
        if n >= 10:
            raise HTTPException(400, "Máximo 10 carteras")
        c.execute("INSERT INTO accounts (user_id, name, kind, start_cash, fee_eur, created) VALUES (?,?,?,?,?,?)",
                  (u["id"], body.name, body.kind, body.start_cash if body.kind == "sim" else 0, body.fee_eur, time.time()))
    return {"ok": True}


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int, u=Depends(current_user)):
    with db.conn() as c:
        c.execute("DELETE FROM accounts WHERE id = ? AND user_id = ?", (account_id, u["id"]))
    return {"ok": True}


@app.get("/api/accounts/{account_id}")
def account_detail(account_id: int, u=Depends(current_user)):
    a, trades = portfolio.get_account(u["id"], account_id)
    if not a:
        raise HTTPException(404, "Cartera no encontrada")
    out = portfolio.compute(a, trades)
    out["trades"] = [dict(t) for t in reversed(trades)][:200]
    return out


@app.get("/api/accounts/{account_id}/history")
def account_history(account_id: int, range: str = "1mo", u=Depends(current_user)):
    if range not in prices.RANGES:
        raise HTTPException(400, "Rango no válido")
    out = portfolio.value_history(u["id"], account_id, range)
    if out is None:
        raise HTTPException(404, "Cartera no encontrada")
    return out


@app.post("/api/accounts/{account_id}/trades")
def add_trade(account_id: int, body: NewTrade, u=Depends(current_user)):
    ts = None
    if body.date:
        try:
            ts = time.mktime(time.strptime(body.date, "%Y-%m-%d")) + 12 * 3600
        except ValueError:
            raise HTTPException(400, "Fecha no válida")
    try:
        return portfolio.trade(u["id"], account_id, body.ticker.upper(), body.side, body.qty, body.amount_eur,
                               body.price, ts, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/accounts/{account_id}/trades/{trade_id}")
def delete_trade(account_id: int, trade_id: int, u=Depends(current_user)):
    a, _ = portfolio.get_account(u["id"], account_id)
    if not a:
        raise HTTPException(404, "Cartera no encontrada")
    if a["kind"] == "sim":
        raise HTTPException(400, "En el simulador no se pueden borrar operaciones: vende para deshacer")
    with db.conn() as c:
        c.execute("DELETE FROM trades WHERE id = ? AND account_id = ?", (trade_id, account_id))
    return {"ok": True}


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# ---------------------------------------------------------------- web
app.mount("/", StaticFiles(directory=ROOT / "docs", html=True), name="web")
