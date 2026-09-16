import argparse
import csv
import io
import json
import secrets
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "quiz_results.db"
ADMIN_PASSWORD = "hfgdmm"
SESSION_COOKIE = "agro_admin_session"
admin_sessions = set()

GAMES = {
    "quiz1": {"name": "农业知识答题闯关", "file": "index.html"},
    "quiz2": {"name": "智慧农业闯关", "file": "smart-farm-quiz.html"},
}
DEFAULT_GAME = "quiz1"

app = FastAPI(title="农业互动展示")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            ip TEXT NOT NULL,
            user_agent TEXT,
            score INTEGER NOT NULL,
            right_count INTEGER NOT NULL,
            total INTEGER NOT NULL,
            rate INTEGER NOT NULL,
            grade TEXT,
            answers_json TEXT NOT NULL DEFAULT '[]',
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_results_ip ON quiz_results(ip)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_results_time ON quiz_results(submitted_at)")
        c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_runs(
            run_id TEXT PRIMARY KEY,
            terminal_id TEXT NOT NULL,
            game TEXT NOT NULL,
            ip TEXT NOT NULL,
            client_port INTEGER,
            user_agent TEXT,
            status TEXT NOT NULL DEFAULT 'playing',
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_active_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            answered_count INTEGER NOT NULL DEFAULT 0,
            right_count INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            rate INTEGER NOT NULL DEFAULT 0,
            grade TEXT,
            answers_json TEXT NOT NULL DEFAULT '[]'
        )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_runs_terminal ON quiz_runs(terminal_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_runs_active ON quiz_runs(last_active_at)")
        c.execute("""
        CREATE TABLE IF NOT EXISTS app_settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        c.execute(
            "INSERT OR IGNORE INTO app_settings(key,value) VALUES('active_game',?)",
            (DEFAULT_GAME,),
        )
        c.execute("""
        INSERT OR IGNORE INTO quiz_runs(
          run_id,terminal_id,game,ip,user_agent,status,started_at,last_active_at,finished_at,
          answered_count,right_count,total,score,rate,grade,answers_json
        )
        SELECT 'legacy-'||id, 'legacy-'||COALESCE(NULLIF(session_id,''),id),
          CASE WHEN grade LIKE '方案2%' THEN 'quiz2' ELSE 'quiz1' END,
          ip,user_agent,'finished',submitted_at,submitted_at,submitted_at,total,right_count,total,score,rate,grade,answers_json
        FROM quiz_results
        """)


@app.on_event("startup")
def startup():
    init_db()


def get_active_game() -> str:
    with db() as c:
        row = c.execute("SELECT value FROM app_settings WHERE key='active_game'").fetchone()
    value = row["value"] if row else DEFAULT_GAME
    return value if value in GAMES else DEFAULT_GAME


def set_active_game(game: str):
    if game not in GAMES:
        raise HTTPException(status_code=400, detail="unknown game")
    with db() as c:
        c.execute(
            "INSERT INTO app_settings(key,value) VALUES('active_game',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (game,),
        )


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()[:64]
    xr = request.headers.get("x-real-ip")
    if xr:
        return xr.strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def require_admin(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token or token not in admin_sessions:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/")
def home():
    game = get_active_game()
    html = (STATIC_DIR / GAMES[game]["file"]).read_text(encoding="utf-8")
    marker = f'<script>window.__ACTIVE_GAME__={json.dumps(game)};</script><script src="/static/tracking.js"></script><script src="/static/mode-watch.js"></script>'
    html = html.replace("</body>", marker + "</body>")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/api/active-game")
def public_active_game():
    game = get_active_game()
    return {"active_game": game, "name": GAMES[game]["name"]}


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.post("/api/runs/start")
async def start_run(request: Request):
    data = await request.json()
    run_id = str(data.get("run_id", ""))[:128]
    terminal_id = str(data.get("terminal_id", ""))[:128]
    game = str(data.get("game", ""))[:32]
    total = int(data.get("total", 0) or 0)
    if not run_id or not terminal_id or game not in GAMES:
        return JSONResponse({"error":"bad run identity"}, status_code=400)
    port = request.client.port if request.client else None
    with db() as c:
        c.execute("""INSERT OR REPLACE INTO quiz_runs(
          run_id,terminal_id,game,ip,client_port,user_agent,status,started_at,last_active_at,
          answered_count,right_count,total,score,rate,answers_json
        ) VALUES(?,?,?,?,?,?,'playing',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,0,0,?,0,0,'[]')""",
        (run_id,terminal_id,game,client_ip(request),port,request.headers.get("user-agent","")[:500],total))
    return {"ok":True}


@app.post("/api/runs/update")
async def update_run(request: Request):
    data = await request.json()
    run_id = str(data.get("run_id", ""))[:128]
    terminal_id = str(data.get("terminal_id", ""))[:128]
    if not run_id or not terminal_id:
        return JSONResponse({"error":"bad run identity"}, status_code=400)
    status = str(data.get("status", "playing"))
    if status not in ("playing","finished"):
        status = "playing"
    def iv(name,default=0):
        try: return int(data.get(name,default) or 0)
        except Exception: return default
    answered,right,total,score,rate = [iv(x) for x in ("answered_count","right_count","total","score","rate")]
    answers=data.get("answers",[])
    if not isinstance(answers,list): answers=[]
    aj=json.dumps(answers[:100],ensure_ascii=False)[:50000]
    with db() as c:
        row=c.execute("SELECT run_id FROM quiz_runs WHERE run_id=? AND terminal_id=?",(run_id,terminal_id)).fetchone()
        if not row:
            return JSONResponse({"error":"run not found"},status_code=404)
        c.execute("""UPDATE quiz_runs SET status=?,last_active_at=CURRENT_TIMESTAMP,
          finished_at=CASE WHEN ?='finished' THEN CURRENT_TIMESTAMP ELSE finished_at END,
          answered_count=?,right_count=?,total=?,score=?,rate=?,grade=?,answers_json=?
          WHERE run_id=? AND terminal_id=?""",
          (status,status,answered,right,total,score,rate,str(data.get("grade", ""))[:100],aj,run_id,terminal_id))
    return {"ok":True}


@app.post("/api/results")
async def save_result(request: Request):
    data = await request.json()
    try:
        score = int(data.get("score", 0))
        right = int(data.get("right_count", 0))
        total = int(data.get("total", 0))
        rate = int(data.get("rate", 0))
    except (TypeError, ValueError):
        return JSONResponse({"error": "bad numeric fields"}, status_code=400)
    if total <= 0 or total > 100 or right < 0 or right > total or score < 0 or score > 100 or rate < 0 or rate > 100:
        return JSONResponse({"error": "bad result"}, status_code=400)
    answers = data.get("answers", [])
    if not isinstance(answers, list):
        answers = []
    answers_json = json.dumps(answers[:100], ensure_ascii=False)[:50000]
    with db() as c:
        c.execute("""INSERT INTO quiz_results
          (session_id,ip,user_agent,score,right_count,total,rate,grade,answers_json)
          VALUES(?,?,?,?,?,?,?,?,?)""", (
            str(data.get("session_id", ""))[:128],
            client_ip(request),
            request.headers.get("user-agent", "")[:500],
            score, right, total, rate, str(data.get("grade", ""))[:100], answers_json
        ))
    return {"ok": True}


@app.post("/api/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    if str(data.get("password", "")) != ADMIN_PASSWORD:
        return JSONResponse({"ok": False, "error": "密码错误"}, status_code=401)
    token = secrets.token_urlsafe(32)
    admin_sessions.add(token)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", max_age=86400)
    return resp


@app.post("/api/admin/logout")
def admin_logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        admin_sessions.discard(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/api/admin/dashboard")
def dashboard(request: Request):
    require_admin(request)
    active_game = get_active_game()
    with db() as c:
        s = c.execute("""SELECT
          COUNT(*) AS total_runs,
          COUNT(DISTINCT CASE WHEN terminal_id NOT LIKE 'legacy-%' THEN terminal_id END) AS unique_terminals,
          SUM(CASE WHEN status='finished' THEN 1 ELSE 0 END) AS finished_runs,
          SUM(CASE WHEN status='playing' AND last_active_at >= datetime('now','-90 seconds') THEN 1 ELSE 0 END) AS active_runs,
          SUM(CASE WHEN status='playing' AND last_active_at < datetime('now','-90 seconds') THEN 1 ELSE 0 END) AS abandoned_runs,
          ROUND(AVG(CASE WHEN status='finished' THEN score END),1) AS avg_score,
          ROUND(AVG(CASE WHEN status='finished' THEN rate END),1) AS avg_rate,
          SUM(CASE WHEN status='finished' AND rate=100 THEN 1 ELSE 0 END) AS perfect_runs
          FROM quiz_runs""").fetchone()
        rows = c.execute("""SELECT run_id,terminal_id,game,ip,client_port,status,started_at,last_active_at,finished_at,
          answered_count,right_count,total,score,rate,grade,user_agent,
          CASE WHEN status='finished' THEN 'finished'
               WHEN last_active_at < datetime('now','-90 seconds') THEN 'abandoned'
               ELSE 'playing' END AS display_status
          FROM quiz_runs ORDER BY started_at DESC LIMIT 500""").fetchall()
    return {
        "summary": dict(s),
        "results": [dict(r) for r in rows],
        "active_game": active_game,
        "games": [{"id": gid, "name": meta["name"]} for gid, meta in GAMES.items()],
    }


@app.post("/api/admin/active-game")
async def change_active_game(request: Request):
    require_admin(request)
    data = await request.json()
    game = str(data.get("game", ""))
    set_active_game(game)
    return {"ok": True, "active_game": game, "name": GAMES[game]["name"]}


@app.get("/api/admin/result/{run_id}")
def result_detail(run_id: str, request: Request):
    require_admin(request)
    with db() as c:
        row = c.execute("SELECT * FROM quiz_runs WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    d = dict(row)
    try:
        d["answers"] = json.loads(d.pop("answers_json"))
    except Exception:
        d["answers"] = []
        d.pop("answers_json", None)
    return d


@app.get("/api/admin/export.csv")
def export_csv(request: Request):
    require_admin(request)
    with db() as c:
        rows = c.execute("""SELECT run_id,terminal_id,game,ip,client_port,status,started_at,last_active_at,finished_at,
          answered_count,right_count,total,score,rate,grade FROM quiz_runs ORDER BY started_at DESC""").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Run ID","终端ID","方案","IP","起始端口","状态","开始时间","最后活动","完成时间","已答","答对","总题数","得分","正确率","等级"])
    for r in rows: w.writerow(list(r))
    data='\ufeff'+buf.getvalue()
    return Response(data,media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=quiz_runs.csv"})


def main():
    p = argparse.ArgumentParser(description="农业互动展示服务器")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8831)
    args = p.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
