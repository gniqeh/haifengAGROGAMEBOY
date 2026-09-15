import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "agrogameboy.db"
QUESTIONS_PATH = BASE_DIR / "questions.json"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="haifengAGROGAMEBOY")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

participant_sockets: Set[WebSocket] = set()
admin_sockets: Set[WebSocket] = set()


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                status TEXT NOT NULL DEFAULT 'waiting',
                current_question INTEGER NOT NULL DEFAULT 0,
                revealed INTEGER NOT NULL DEFAULT 0
            );
            INSERT OR IGNORE INTO app_state(id, status, current_question, revealed)
            VALUES (1, 'waiting', 0, 0);

            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                ip TEXT,
                first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS votes (
                device_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                answer_index INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(device_id, question_id)
            );
            """
        )


def load_questions():
    with QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_state():
    questions = load_questions()
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM app_state WHERE id=1").fetchone()
        state = dict(row)
        qidx = state["current_question"]
        question = questions[qidx] if 0 <= qidx < len(questions) else None
        counts = []
        answered = 0
        if question:
            qid = question["id"]
            answered = conn.execute(
                "SELECT COUNT(*) FROM votes WHERE question_id=?", (qid,)
            ).fetchone()[0]
            for i, _ in enumerate(question["options"]):
                c = conn.execute(
                    "SELECT COUNT(*) FROM votes WHERE question_id=? AND answer_index=?",
                    (qid, i),
                ).fetchone()[0]
                counts.append(c)
        device_total = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    return {
        "status": state["status"],
        "current_question": qidx,
        "revealed": bool(state["revealed"]),
        "question": question,
        "counts": counts,
        "answered": answered,
        "registered_devices": device_total,
        "online": len(participant_sockets),
        "total_questions": len(questions),
    }


async def broadcast(payload: dict):
    dead = []
    for ws in list(participant_sockets | admin_sockets):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        participant_sockets.discard(ws)
        admin_sockets.discard(ws)


async def broadcast_state():
    await broadcast({"type": "state", "data": get_state()})


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/api/state")
def api_state():
    return get_state()


@app.post("/api/register")
async def register(request: Request):
    data = await request.json()
    device_id = str(data.get("device_id", "")).strip()
    if not device_id:
        return JSONResponse({"ok": False, "error": "missing device_id"}, status_code=400)
    ip = request.client.host if request.client else ""
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO devices(device_id, ip) VALUES (?, ?)
            ON CONFLICT(device_id) DO UPDATE SET ip=excluded.ip, last_seen=CURRENT_TIMESTAMP
            """,
            (device_id, ip),
        )
    return {"ok": True}


@app.get("/api/my-vote/{device_id}")
def my_vote(device_id: str):
    state = get_state()
    q = state["question"]
    if not q:
        return {"answer_index": None}
    with db_conn() as conn:
        row = conn.execute(
            "SELECT answer_index FROM votes WHERE device_id=? AND question_id=?",
            (device_id, q["id"]),
        ).fetchone()
    return {"answer_index": row[0] if row else None}


@app.post("/api/vote")
async def vote(request: Request):
    data = await request.json()
    device_id = str(data.get("device_id", "")).strip()
    answer_index = data.get("answer_index")
    state = get_state()
    q = state["question"]
    if state["status"] != "running" or not q:
        return JSONResponse({"ok": False, "error": "not running"}, status_code=409)
    if not isinstance(answer_index, int) or not 0 <= answer_index < len(q["options"]):
        return JSONResponse({"ok": False, "error": "invalid answer"}, status_code=400)
    ip = request.client.host if request.client else ""
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO devices(device_id, ip) VALUES (?, ?)
            ON CONFLICT(device_id) DO UPDATE SET ip=excluded.ip, last_seen=CURRENT_TIMESTAMP
            """,
            (device_id, ip),
        )
        conn.execute(
            """
            INSERT INTO votes(device_id, question_id, answer_index)
            VALUES (?, ?, ?)
            ON CONFLICT(device_id, question_id)
            DO UPDATE SET answer_index=excluded.answer_index, updated_at=CURRENT_TIMESTAMP
            """,
            (device_id, q["id"], answer_index),
        )
    await broadcast_state()
    return {"ok": True}


@app.post("/api/admin/{action}")
async def admin_action(action: str):
    questions = load_questions()
    with db_conn() as conn:
        state = conn.execute("SELECT * FROM app_state WHERE id=1").fetchone()
        idx = state["current_question"]
        if action == "start":
            conn.execute("UPDATE app_state SET status='running', current_question=0, revealed=0 WHERE id=1")
        elif action == "next":
            idx = min(idx + 1, max(0, len(questions) - 1))
            conn.execute("UPDATE app_state SET status='running', current_question=?, revealed=0 WHERE id=1", (idx,))
        elif action == "prev":
            idx = max(0, idx - 1)
            conn.execute("UPDATE app_state SET status='running', current_question=?, revealed=0 WHERE id=1", (idx,))
        elif action == "reveal":
            conn.execute("UPDATE app_state SET revealed=1 WHERE id=1")
        elif action == "hide":
            conn.execute("UPDATE app_state SET revealed=0 WHERE id=1")
        elif action == "finish":
            conn.execute("UPDATE app_state SET status='finished', revealed=1 WHERE id=1")
        elif action == "waiting":
            conn.execute("UPDATE app_state SET status='waiting', revealed=0 WHERE id=1")
        elif action == "reset":
            conn.execute("DELETE FROM votes")
            conn.execute("DELETE FROM devices")
            conn.execute("UPDATE app_state SET status='waiting', current_question=0, revealed=0 WHERE id=1")
        else:
            return JSONResponse({"ok": False, "error": "unknown action"}, status_code=404)
    await broadcast_state()
    return {"ok": True, "state": get_state()}


@app.get("/api/admin/devices")
def admin_devices():
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT device_id, ip, first_seen, last_seen FROM devices ORDER BY first_seen"
        ).fetchall()
    return [dict(r) for r in rows]


@app.websocket("/ws/participant/{device_id}")
async def ws_participant(websocket: WebSocket, device_id: str):
    await websocket.accept()
    participant_sockets.add(websocket)
    try:
        await websocket.send_json({"type": "state", "data": get_state()})
        await broadcast_state()
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        participant_sockets.discard(websocket)
        await broadcast_state()


@app.websocket("/ws/admin")
async def ws_admin(websocket: WebSocket):
    await websocket.accept()
    admin_sockets.add(websocket)
    try:
        await websocket.send_json({"type": "state", "data": get_state()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        admin_sockets.discard(websocket)
