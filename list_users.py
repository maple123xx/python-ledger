"""List account names from the same database used by the web app."""

import sqlite3

from ledger.config import database_path


def main() -> None:
    path = database_path()
    print(f"数据库：{path}")
    if not path.is_file():
        print("数据库文件不存在。请先启动网页并注册账号。")
        return
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
        users = db.execute("SELECT id, username FROM users ORDER BY id").fetchall()
    if not users:
        print("暂无注册用户。")
    for user_id, username in users:
        print(f"ID: {user_id}，用户名: {username}")
    print("密码原文不会保存在数据库中。")


if __name__ == "__main__":
    main()
