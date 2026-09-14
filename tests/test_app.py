import sqlite3

from fastapi.testclient import TestClient

from ledger.app import create_app
from ledger.config import PROJECT_DIR, database_path


def register(client, username):
    response = client.post("/register", data={"username": username, "password": "correct-password"}, follow_redirects=False)
    assert response.status_code == 303


def test_login_logout_and_password_hash(tmp_path):
    db_path = tmp_path / "ledger.db"
    with TestClient(create_app(db_path)) as client:
        register(client, "alice")
        with sqlite3.connect(db_path) as db:
            stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
        assert "correct-password" not in stored
        assert stored.startswith("scrypt$")
        assert "alice" in client.get("/").text
        client.post("/logout")
        assert client.post("/entries", data={"kind": "income", "amount": "1"}).status_code == 401
        assert "用户名或密码错误" in client.post("/login", data={"username": "alice", "password": "wrong"}).text
        assert client.post("/login", data={"username": "alice", "password": "correct-password"}, follow_redirects=False).status_code == 303
        assert "alice" in client.get("/").text


def test_isolation_and_persistence(tmp_path):
    db_path = tmp_path / "ledger.db"
    app = create_app(db_path)
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "alice")
        register(bob, "bob")
        assert alice.post("/entries", data={"kind": "income", "amount": "12.50", "note": "Alice secret"}, follow_redirects=False).status_code == 303
        assert alice.post("/entries", data={"kind": "expense", "amount": "2.01", "note": "Lunch"}, follow_redirects=False).status_code == 303
        assert "¥10.49" in alice.get("/").text
        assert "Alice secret" not in bob.get("/").text
        assert "¥0.00" in bob.get("/").text
        assert bob.post("/entries", data={"kind": "income", "amount": "3", "note": "Bob only"}, follow_redirects=False).status_code == 303
        assert "Bob only" not in alice.get("/").text
    with TestClient(create_app(db_path)) as reopened:
        reopened.post("/login", data={"username": "alice", "password": "correct-password"})
        assert "¥10.49" in reopened.get("/").text
        assert "Alice secret" in reopened.get("/").text


def test_invalid_entries_are_rejected(tmp_path):
    with TestClient(create_app(tmp_path / "ledger.db")) as client:
        register(client, "alice")
        for amount in ("0", "-1", "1.234", "1e3", "10000000001", "abc"):
            response = client.post("/entries", data={"kind": "income", "amount": amount})
            assert "role='alert'" in response.text
        assert "类型无效" in client.post("/entries", data={"kind": "other", "amount": "1"}).text
        assert "备注不能超过" in client.post("/entries", data={"kind": "income", "amount": "1", "note": "x" * 201}).text
        assert "¥0.00" in client.get("/").text


def test_history_pagination_and_escaped_notes(tmp_path):
    db_path = tmp_path / "ledger.db"
    with TestClient(create_app(db_path)) as client:
        register(client, "alice")
        for number in range(25):
            client.post("/entries", data={"kind": "income", "amount": "1", "note": f"item-{number}"})
        client.post("/entries", data={"kind": "expense", "amount": "0.50", "note": "<script>alert(1)</script>"})
        first = client.get("/").text
        second = client.get("/?page_number=2").text
        assert "¥24.50" in first
        assert "item-24" in first and "item-0" not in first
        assert "item-0" in second and "item-24" not in second
        assert "&lt;script&gt;" in first and "<script>" not in first


def test_default_database_path_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("LEDGER_DB", raising=False)
    monkeypatch.chdir(tmp_path)
    assert database_path() == PROJECT_DIR / "ledger.db"
    assert database_path(tmp_path / "other.db") == tmp_path / "other.db"
