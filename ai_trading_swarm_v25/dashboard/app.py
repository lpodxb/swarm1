from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from state.global_state import get_global_state
from lab.storage import init_db, get_strategies_summary
from journal.storage import init_db as init_journal_db
from journal.storage import fetch_recent as fetch_journal_recent

app = FastAPI(title="AI Trading Swarm v2.5 Dashboard")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

_global_state = None


@app.on_event("startup")
async def startup_event():
    global _global_state
    if _global_state is None:
        _global_state = get_global_state()
    init_db()
    init_journal_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/summary", response_class=JSONResponse)
async def api_summary():
    s = _global_state
    regime = s.market_regime.regime
    last_equity = s.equity_curve[-1]["daily_pnl"] if s.equity_curve else 0.0
    data: Dict[str, Any] = {
        "trades_executed": s.trades_executed,
        "trades_rejected": s.trades_rejected,
        "daily_pnl": last_equity,
        "regime": regime,
        "is_trading_paused": s.is_trading_paused,
        "updated_at": datetime.utcnow().isoformat(),
    }
    return JSONResponse(data)


@app.get("/api/consistency", response_class=JSONResponse)
async def api_consistency():
    return JSONResponse({"status": "ok", "message": "Dashboard and backend are up."})


@app.get("/api/strategies", response_class=JSONResponse)
async def api_strategies():
    items = get_strategies_summary()
    return JSONResponse({"strategies": items})


@app.get("/api/journal/recent", response_class=JSONResponse)
async def api_journal_recent(limit: int = 100):
    items = [r.__dict__ for r in fetch_journal_recent(limit)]
    return JSONResponse({"entries": items})
