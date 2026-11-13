"""Base de datos SQLite del servidor: usuarios, sesiones, invitaciones, carteras y operaciones."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("INVERSIONES_DB", Path(__file__).resolve().parent.parent / "data" / "servidor.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL COLLATE NOCASE,
  pass_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS invites (
  code TEXT PRIMARY KEY,
  created_by INTEGER REFERENCES users(id),
  used_by INTEGER REFERENCES users(id),
  created REAL NOT NULL
);
-- kind: 'sim' (dinero ficticio) o 'real' (registro de tus operaciones reales)
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('sim','real')),
  start_cash REAL NOT NULL DEFAULT 0,
  fee_eur REAL NOT NULL DEFAULT 1.0,
  created REAL NOT NULL
);
-- Cada operación guarda el precio en su moneda y el cambio a euros en ese momento
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  ts REAL NOT NULL,
  ticker TEXT NOT NULL,
  name TEXT,
  side TEXT NOT NULL CHECK (side IN ('buy','sell')),
  qty REAL NOT NULL CHECK (qty > 0),
  price REAL NOT NULL CHECK (price > 0),
  currency TEXT NOT NULL,
  fx_eur REAL NOT NULL,          -- unidades de moneda por 1 EUR (USD por EUR, etc.)
  fee_eur REAL NOT NULL DEFAULT 0,
  note TEXT
);
CREATE INDEX IF NOT EXISTS trades_account ON trades(account_id, ts);
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


# ---------------------------------------------------------------- contraseñas
# scrypt si el sistema lo tiene; si no, PBKDF2-SHA256 con 600.000 iteraciones (recomendación OWASP).
PBKDF2_ITER = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    if hasattr(hashlib, "scrypt"):
        h = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
        return f"scrypt${salt.hex()}${h.hex()}"
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITER)
    return f"pbkdf2${PBKDF2_ITER}${salt.hex()}${h.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if parts[0] == "scrypt":
            calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(parts[1]), n=2 ** 14, r=8, p=1, dklen=32)
            return hmac.compare_digest(calc.hex(), parts[2])
        if parts[0] == "pbkdf2":
            calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(parts[2]), int(parts[1]))
            return hmac.compare_digest(calc.hex(), parts[3])
    except Exception:
        pass
    return False


# ---------------------------------------------------------------- usuarios y sesiones
SESSION_DAYS = 60


def create_user(username: str, password: str, is_admin=False) -> int:
    with conn() as c:
        cur = c.execute("INSERT INTO users (username, pass_hash, is_admin, created) VALUES (?,?,?,?)",
                        (username.strip(), hash_password(password), int(is_admin), time.time()))
        uid = cur.lastrowid
        # Cada usuario empieza con una cartera ficticia de 10.000 €
        c.execute("INSERT INTO accounts (user_id, name, kind, start_cash, fee_eur, created) VALUES (?,?,?,?,?,?)",
                  (uid, "Simulador", "sim", 10000.0, 1.0, time.time()))
        return uid


def login(username: str, password: str):
    with conn() as c:
        u = c.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        if not u or not check_password(password, u["pass_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        c.execute("INSERT INTO sessions VALUES (?,?,?)", (token, u["id"], time.time() + SESSION_DAYS * 86400))
        c.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        return token


def user_from_token(token: str):
    if not token:
        return None
    with conn() as c:
        return c.execute("""SELECT u.id, u.username, u.is_admin FROM sessions s JOIN users u ON u.id = s.user_id
                            WHERE s.token = ? AND s.expires > ?""", (token, time.time())).fetchone()


def logout(token: str):
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


def new_invite(created_by: int) -> str:
    code = secrets.token_hex(4).upper()
    with conn() as c:
        c.execute("INSERT INTO invites VALUES (?,?,NULL,?)", (code, created_by, time.time()))
    return code


def use_invite(code: str, username: str, password: str):
    with conn() as c:
        inv = c.execute("SELECT * FROM invites WHERE code = ? AND used_by IS NULL", (code.strip().upper(),)).fetchone()
        if not inv:
            return None
    uid = create_user(username, password)
    with conn() as c:
        c.execute("UPDATE invites SET used_by = ? WHERE code = ?", (uid, code.strip().upper()))
    return uid
