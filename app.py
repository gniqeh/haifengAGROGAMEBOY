import argparse
import csv
import io
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "quiz_results.db"
ADMIN_PASSWORD = "hfgdmm"
SESSION_COOKIE = "agro_admin_session"
admin_sessions = set()

app = FastAPI(title="农业知识答题闯关")
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

@app.on_event("startup")
def startup():
    init_db()

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
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")

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
    with db() as c:
        s = c.execute("""SELECT COUNT(*) AS total_runs, COUNT(DISTINCT ip) AS unique_ips,
          ROUND(AVG(score),1) AS avg_score, ROUND(AVG(rate),1) AS avg_rate,
          SUM(CASE WHEN rate=100 THEN 1 ELSE 0 END) AS perfect_runs
          FROM quiz_results""").fetchone()
        rows = c.execute("""SELECT id,submitted_at,ip,score,right_count,total,rate,grade,user_agent,session_id
          FROM quiz_results ORDER BY id DESC LIMIT 500""").fetchall()
    return {"summary": dict(s), "results": [dict(r) for r in rows]}

@app.get("/api/admin/result/{result_id}")
def result_detail(result_id: int, request: Request):
    require_admin(request)
    with db() as c:
        row = c.execute("SELECT * FROM quiz_results WHERE id=?", (result_id,)).fetchone()
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
        rows = c.execute("""SELECT id,submitted_at,ip,score,right_count,total,rate,grade,user_agent,session_id
          FROM quiz_results ORDER BY id DESC""").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID","提交时间","IP","得分","答对","总题数","正确率","等级","User-Agent","Session ID"])
    for r in rows:
        w.writerow(list(r))
    data = '\ufeff' + buf.getvalue()
    return Response(data, media_type="text/csv; charset=utf-8", headers={"Content-Disposition":"attachment; filename=quiz_results.csv"})

def main():
    p = argparse.ArgumentParser(description="农业知识答题闯关服务器")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8831)
    args = p.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
