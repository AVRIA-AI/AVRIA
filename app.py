import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()
BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "avria.sqlite3"
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

app = FastAPI(title="AVRIA AI Trading API", version="0.2.0")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(db()) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS accounts (
            user_id TEXT PRIMARY KEY, balance REAL NOT NULL DEFAULT 10000
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, market TEXT NOT NULL, asset TEXT NOT NULL,
            side TEXT NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL,
            pnl REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            closed_at TEXT
        )""")
        conn.commit()


@app.on_event("startup")
def startup():
    init_db()


async def get_user_id(request: Request) -> str:
    # Development mode is for local testing only. Production must verify Telegram initData.
    if DEV_MODE:
        return request.headers.get("X-Demo-User", "demo-user")
    raise HTTPException(401, "Telegram Mini App authentication is not configured")


def ensure_account(conn, user_id: str):
    conn.execute("INSERT OR IGNORE INTO accounts(user_id, balance) VALUES(?, 10000)", (user_id,))


class TradeRequest(BaseModel):
    market: str = Field(pattern="^(Cryptocurrency|Forex|Stock Market)$")
    asset: str = Field(min_length=3, max_length=30)
    side: str = Field(pattern="^(BUY|SELL)$")
    amount: float = Field(gt=0, le=10000)


class CloseTradeRequest(BaseModel):
    pnl: float = Field(ge=-10000, le=10000)


@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/account")
async def account(request: Request):
    user_id = await get_user_id(request)
    with closing(db()) as conn:
        ensure_account(conn, user_id)
        acc = conn.execute("SELECT balance FROM accounts WHERE user_id=?", (user_id,)).fetchone()
        trades = conn.execute("SELECT status, COUNT(*) n FROM trades WHERE user_id=? GROUP BY status", (user_id,)).fetchall()
        counts = {r["status"]: r["n"] for r in trades}
        open_rows = conn.execute("SELECT COALESCE(SUM(amount),0) total FROM trades WHERE user_id=? AND status='OPEN'", (user_id,)).fetchone()
        pnl = conn.execute("SELECT COALESCE(SUM(pnl),0) total FROM trades WHERE user_id=? AND status='CLOSED'", (user_id,)).fetchone()
        conn.commit()
        return {"balance": acc["balance"], "open": counts.get("OPEN", 0),
                "closed": counts.get("CLOSED", 0), "invested": open_rows["total"],
                "realized_pnl": pnl["total"], "portfolio_value": acc["balance"] + open_rows["total"] + pnl["total"]}


@app.get("/api/trades")
async def list_trades(request: Request):
    user_id = await get_user_id(request)
    with closing(db()) as conn:
        rows = conn.execute("""SELECT id, market, asset, side, amount, status, pnl, created_at, closed_at
                               FROM trades WHERE user_id=? ORDER BY id DESC LIMIT 100""", (user_id,)).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/trades")
async def create_trade(payload: TradeRequest, request: Request):
    user_id = await get_user_id(request)
    with closing(db()) as conn:
        ensure_account(conn, user_id)
        acc = conn.execute("SELECT balance FROM accounts WHERE user_id=?", (user_id,)).fetchone()
        if payload.amount > acc["balance"]:
            raise HTTPException(400, "Insufficient demo balance")
        conn.execute("UPDATE accounts SET balance=balance-? WHERE user_id=?", (payload.amount, user_id))
        cur = conn.execute("""INSERT INTO trades(user_id,market,asset,side,amount,status)
                              VALUES(?,?,?,?,?,'OPEN')""",
                           (user_id, payload.market, payload.asset, payload.side, payload.amount))
        conn.commit()
        return {"ok": True, "trade_id": cur.lastrowid, "message": "Demo trade opened"}


@app.post("/api/trades/{trade_id}/close")
async def close_trade(trade_id: int, payload: CloseTradeRequest, request: Request):
    user_id = await get_user_id(request)
    with closing(db()) as conn:
        row = conn.execute("SELECT amount,status FROM trades WHERE id=? AND user_id=?", (trade_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, "Trade not found")
        if row["status"] != "OPEN":
            raise HTTPException(400, "Trade is already closed")
        returned = max(0, row["amount"] + payload.pnl)
        conn.execute("UPDATE accounts SET balance=balance+? WHERE user_id=?", (returned, user_id))
        conn.execute("UPDATE trades SET status='CLOSED',pnl=?,closed_at=CURRENT_TIMESTAMP WHERE id=?",
                     (payload.pnl, trade_id))
        conn.commit()
        return {"ok": True, "returned_to_balance": returned}


@app.get("/health")
def health():
    return {"status": "ok", "app": "AVRIA", "version": "0.2.0"}
