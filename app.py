import json
import random
import sqlite3
from pathlib import Path
from typing import Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "agrogameboy.db"
STATIC_DIR = BASE_DIR / "static"
SCENARIOS_PATH = BASE_DIR / "scenarios.json"

app = FastAPI(title="AGRO GAMEBOY")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
admins: Set[WebSocket] = set()
participants: Set[WebSocket] = set()


def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def scenarios():
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS devices(
          device_id TEXT PRIMARY KEY, ip TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
          last_seen TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS runs(
          device_id TEXT PRIMARY KEY, scenario_id INTEGER NOT NULL, stage TEXT NOT NULL DEFAULT 'survey',
          selected_zone INTEGER DEFAULT 0, water_json TEXT NOT NULL DEFAULT '[0,0,0,0]',
          fert_json TEXT NOT NULL DEFAULT '[0,0,0,0]', ai_mode TEXT DEFAULT '', event_action TEXT DEFAULT '',
          score REAL, yield_value REAL, profit REAL, efficiency REAL, risk REAL,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)


@app.on_event("startup")
def startup():
    init_db()


def ensure_run(device_id: str):
    ss = scenarios()
    with db() as c:
        row = c.execute("SELECT * FROM runs WHERE device_id=?", (device_id,)).fetchone()
        if not row:
            sid = (abs(hash(device_id)) % len(ss)) + 1
            c.execute("INSERT INTO runs(device_id,scenario_id) VALUES(?,?)", (device_id, sid))
            row = c.execute("SELECT * FROM runs WHERE device_id=?", (device_id,)).fetchone()
    return row


def run_payload(device_id: str):
    row = ensure_run(device_id)
    sc = next(s for s in scenarios() if s["id"] == row["scenario_id"])
    return {
        "device_id": device_id,
        "stage": row["stage"],
        "selected_zone": row["selected_zone"],
        "water": json.loads(row["water_json"]),
        "fert": json.loads(row["fert_json"]),
        "ai_mode": row["ai_mode"],
        "event_action": row["event_action"],
        "score": row["score"], "yield": row["yield_value"], "profit": row["profit"],
        "efficiency": row["efficiency"], "risk": row["risk"],
        "scenario": sc,
    }


def calc_result(sc, water, fert, ai_mode, event_action):
    water_err = sum(abs(a-b) for a,b in zip(water, sc["ai"]["water"]))
    fert_err = sum(abs(a-b) for a,b in zip(fert, sc["ai"]["fert"]))
    resource_fit = max(0, 100 - water_err*0.55 - fert_err*0.7)
    event_scores = sc["event"]["scores"]
    event_score = event_scores.get(event_action, 40)
    ai_bonus = {"keep": 0, "adopt": 5, "adjust": 3}.get(ai_mode, 0)
    score = max(0, min(100, resource_fit*0.58 + event_score*0.34 + ai_bonus + 7))
    yield_value = round(sc["base_yield"] * (0.82 + score/500), 1)
    efficiency = round(max(40, min(99, 62 + resource_fit*0.34)), 1)
    risk = round(max(4, min(70, 62 - event_score*0.5 - score*0.12)), 1)
    profit = round(yield_value * sc["price"] - sc["base_cost"] - sum(water)*0.55 - sum(fert)*1.25, 0)
    return round(score,1), yield_value, profit, efficiency, risk


async def broadcast_admin():
    payload = {"type":"dashboard"}
    dead=[]
    for ws in list(admins):
        try: await ws.send_json(payload)
        except Exception: dead.append(ws)
    for ws in dead: admins.discard(ws)


@app.get("/")
def home(): return FileResponse(STATIC_DIR / "index.html")

@app.get("/admin")
def admin_page(): return FileResponse(STATIC_DIR / "admin.html")

@app.post("/api/register")
async def register(request: Request):
    data = await request.json(); did = str(data.get("device_id","")).strip()
    if not did: return JSONResponse({"error":"missing device_id"},400)
    ip = request.client.host if request.client else ""
    with db() as c:
        c.execute("""INSERT INTO devices(device_id,ip) VALUES(?,?)
        ON CONFLICT(device_id) DO UPDATE SET ip=excluded.ip,last_seen=CURRENT_TIMESTAMP""", (did,ip))
    ensure_run(did)
    await broadcast_admin()
    return {"ok":True, "state":run_payload(did)}

@app.get("/api/game/{device_id}")
def game(device_id: str): return run_payload(device_id)

@app.post("/api/game/{device_id}/save")
async def save_game(device_id: str, request: Request):
    data = await request.json(); state = run_payload(device_id); sc = state["scenario"]
    stage = data.get("stage", state["stage"])
    zone = int(data.get("selected_zone", state["selected_zone"]))
    water = data.get("water", state["water"]); fert = data.get("fert", state["fert"])
    ai_mode = data.get("ai_mode", state["ai_mode"]); event_action = data.get("event_action", state["event_action"])
    if len(water)!=4 or len(fert)!=4: return JSONResponse({"error":"bad resource vector"},400)
    if sum(water) > sc["resources"]["water"] or sum(fert) > sc["resources"]["fert"]:
        return JSONResponse({"error":"resource exceeded"},400)
    result=(None,None,None,None,None)
    if stage == "result": result = calc_result(sc, water, fert, ai_mode, event_action)
    with db() as c:
        c.execute("""UPDATE runs SET stage=?,selected_zone=?,water_json=?,fert_json=?,ai_mode=?,event_action=?,
        score=?,yield_value=?,profit=?,efficiency=?,risk=?,updated_at=CURRENT_TIMESTAMP WHERE device_id=?""",
        (stage,zone,json.dumps(water),json.dumps(fert),ai_mode,event_action,*result,device_id))
    await broadcast_admin()
    return {"ok":True,"state":run_payload(device_id)}

@app.get("/api/admin/dashboard")
def dashboard():
    with db() as c:
        rows=c.execute("""SELECT d.device_id,d.ip,d.first_seen,d.last_seen,r.stage,r.scenario_id,r.score,r.profit
        FROM devices d LEFT JOIN runs r ON d.device_id=r.device_id ORDER BY d.first_seen""").fetchall()
    items=[dict(r) for r in rows]
    done=[x for x in items if x.get("stage")=="result" and x.get("score") is not None]
    return {"online":len(participants),"total":len(items),"done":len(done),"devices":items,
            "avg_score":round(sum(x["score"] for x in done)/len(done),1) if done else None,
            "avg_profit":round(sum(x["profit"] for x in done)/len(done),0) if done else None}

@app.post("/api/admin/reset")
async def reset_all():
    with db() as c:
        c.execute("DELETE FROM runs"); c.execute("DELETE FROM devices")
    await broadcast_admin(); return {"ok":True}

@app.websocket("/ws/admin")
async def ws_admin(ws: WebSocket):
    await ws.accept(); admins.add(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: pass
    finally: admins.discard(ws)

@app.websocket("/ws/participant/{device_id}")
async def ws_participant(ws: WebSocket, device_id: str):
    await ws.accept(); participants.add(ws); await broadcast_admin()
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: pass
    finally:
        participants.discard(ws); await broadcast_admin()
