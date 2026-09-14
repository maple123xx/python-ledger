"""A small, local-first ledger with server-side sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ledger.config import database_path

SESSION_SECONDS = 7 * 24 * 60 * 60
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
AMOUNT_RE = re.compile(r"^[0-9]+(?:\.[0-9]{1,2})?$")
PAGE_SIZE = 20


def create_app(db_path: str | Path | None = None) -> FastAPI:
    database = database_path(db_path)
    database.parent.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="Python 记账本")

    @contextmanager
    def connect():
        db = sqlite3.connect(database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL CHECK(kind IN ('income', 'expense')),
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS entries_user_id_id ON entries(user_id, id DESC);
        """)

    def password_hash(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return f"scrypt${salt.hex()}${digest.hex()}"

    def verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, salt_hex, digest_hex = encoded.split("$")
            if algorithm != "scrypt":
                return False
            actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
            return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
        except (ValueError, TypeError):
            return False

    def current_user(request: Request):
        token = request.cookies.get("ledger_session", "")
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with connect() as db:
            return db.execute("""
                SELECT users.id, users.username FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """, (token_hash, datetime.now(timezone.utc).isoformat())).fetchone()

    def require_user(request: Request):
        user = current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="请先登录")
        return user

    def page(title: str, body: str) -> HTMLResponse:
        return HTMLResponse(f"""<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Python 记账本</title><style>
body{{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 18px;color:#1f2937;background:#f8fafc}}
main{{background:white;padding:24px;border-radius:12px;box-shadow:0 2px 12px #0001}}
label{{display:block;margin:14px 0}}input,select,button{{font:inherit;padding:9px;border:1px solid #cbd5e1;border-radius:6px}}
input{{max-width:100%;box-sizing:border-box}}button{{background:#2563eb;color:white;cursor:pointer}}
table{{border-collapse:collapse;width:100%;margin-top:24px}}th,td{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left}}
.error{{color:#b91c1c}}.muted{{color:#64748b}}nav a{{margin-right:14px}}
</style></head><body><main>{body}</main></body></html>""")

    def money(cents: int) -> str:
        sign = "-" if cents < 0 else ""
        return f"{sign}¥{abs(cents) // 100}.{abs(cents) % 100:02d}"

    def auth_form(mode: str, error: str = "") -> HTMLResponse:
        title = "注册" if mode == "register" else "登录"
        other = "login" if mode == "register" else "register"
        other_label = "已有账号？登录" if mode == "register" else "没有账号？注册"
        return page(title, f"<h1>{title}</h1><p class='error'>{escape(error)}</p>"
                    f"<form method='post' action='/{mode}'>"
                    "<label>用户名 <input name='username' autocomplete='username' required></label>"
                    f"<label>密码 <input type='password' name='password' autocomplete='{'new-password' if mode == 'register' else 'current-password'}' required></label>"
                    f"<button>{title}</button></form><p><a href='/{other}'>{other_label}</a></p>")

    def redirect_home(token: str | None = None) -> RedirectResponse:
        response = RedirectResponse("/", status_code=303)
        if token:
            response.set_cookie("ledger_session", token, max_age=SESSION_SECONDS,
                                httponly=True, samesite="lax", secure=False)
        return response

    def make_session(db: sqlite3.Connection, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)).isoformat()
        db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                   (hashlib.sha256(token.encode()).hexdigest(), user_id, expires))
        return token

    @app.get("/register", response_class=HTMLResponse)
    def register_page():
        return auth_form("register")

    @app.post("/register")
    def register(username: str = Form(...), password: str = Form(...)):
        username = username.strip()
        if not USERNAME_RE.fullmatch(username):
            return auth_form("register", "用户名需为 3–32 位英文字母、数字或下划线")
        if len(password) < 8 or len(password) > 128:
            return auth_form("register", "密码需为 8–128 个字符")
        with connect() as db:
            try:
                cursor = db.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)",
                                    (username, password_hash(password)))
            except sqlite3.IntegrityError:
                return auth_form("register", "用户名已存在")
            token = make_session(db, cursor.lastrowid)
        return redirect_home(token)

    @app.get("/login", response_class=HTMLResponse)
    def login_page():
        return auth_form("login")

    @app.post("/login")
    def login(username: str = Form(...), password: str = Form(...)):
        with connect() as db:
            user = db.execute("SELECT id, password_hash FROM users WHERE username = ?", (username.strip(),)).fetchone()
            if user is None or not verify_password(password, user["password_hash"]):
                return auth_form("login", "用户名或密码错误")
            token = make_session(db, user["id"])
        return redirect_home(token)

    @app.post("/logout")
    def logout(request: Request):
        token = request.cookies.get("ledger_session", "")
        if token:
            with connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("ledger_session")
        return response

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, page_number: int = Query(1, ge=1, le=1_000_000)):
        user = current_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        with connect() as db:
            count = db.execute("SELECT COUNT(*) FROM entries WHERE user_id = ?", (user["id"],)).fetchone()[0]
            total_pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)
            page_number = min(page_number, total_pages)
            entries = db.execute("SELECT kind, amount_cents, note, created_at FROM entries WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                                 (user["id"], PAGE_SIZE, (page_number - 1) * PAGE_SIZE)).fetchall()
            totals = db.execute("""SELECT
                COALESCE(SUM(CASE WHEN kind = 'income' THEN amount_cents ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount_cents ELSE 0 END), 0) AS expense
                FROM entries WHERE user_id = ?""", (user["id"],)).fetchone()
        rows = "".join(f"<tr><td>{escape(row['created_at'][:16].replace('T', ' '))}</td>"
                       f"<td>{'收入' if row['kind'] == 'income' else '支出'}</td>"
                       f"<td>{money(row['amount_cents'])}</td><td>{escape(row['note'])}</td></tr>" for row in entries)
        body = f"<h1>你好，{escape(user['username'])}</h1><form method='post' action='/logout'><button>退出登录</button></form>"
        body += f"<h2>余额：{money(totals['income'] - totals['expense'])}</h2>"
        body += f"<p>总收入：{money(totals['income'])}　总支出：{money(totals['expense'])}</p>"
        error = request.query_params.get("error", "")
        if error:
            body += f"<p class='error' role='alert'>{escape(error[:100])}</p>"
        body += """<h2>新增账目</h2><form method="post" action="/entries">
        <label>类型 <select name="kind"><option value="expense">支出</option><option value="income">收入</option></select></label>
        <label>金额（元） <input name="amount" inputmode="decimal" placeholder="12.50" required></label>
        <label>备注 <input name="note" maxlength="200"></label><button>保存</button></form>
        <h2>明细</h2><p class="muted">时间为 UTC；每页 20 条。</p><table><thead><tr><th>时间</th><th>类型</th><th>金额</th><th>备注</th></tr></thead><tbody>"""
        body += rows + "</tbody></table>"
        body += f"<p>第 {page_number} / {total_pages} 页（共 {count} 条）</p><nav>"
        if page_number > 1:
            body += f"<a href='/?page_number={page_number - 1}'>上一页</a>"
        if page_number < total_pages:
            body += f"<a href='/?page_number={page_number + 1}'>下一页</a>"
        body += "</nav>"
        return page("账本", body)

    @app.post("/entries")
    def add_entry(request: Request, kind: str = Form(...), amount: str = Form(...), note: str = Form("")):
        user = require_user(request)
        def invalid(message: str) -> RedirectResponse:
            return RedirectResponse(f"/?error={quote(message)}", status_code=303)

        if kind not in ("income", "expense"):
            return invalid("类型无效")
        if not AMOUNT_RE.fullmatch(amount):
            return invalid("金额必须是最多两位小数的正数")
        try:
            cents = int(Decimal(amount) * 100)
        except InvalidOperation:
            return invalid("金额无效")
        if not 0 < cents <= 10**12:
            return invalid("金额超出范围")
        note = note.strip()
        if len(note) > 200:
            return invalid("备注不能超过 200 字")
        with connect() as db:
            db.execute("INSERT INTO entries(user_id, kind, amount_cents, note, created_at) VALUES (?, ?, ?, ?, ?)",
                       (user["id"], kind, cents, note, datetime.now(timezone.utc).isoformat()))
        return redirect_home()

    return app


app = create_app()
