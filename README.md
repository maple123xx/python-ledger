# Python 记账本（本地版）

这是一个与现有 JavaScript/Cloudflare 项目完全分开的 FastAPI + SQLite 记账应用。支持注册、登录、退出、按用户隔离账目、添加收入/支出和备注，以及查看余额、收入/支出合计和分页明细（每页 20 条，时间显示为 UTC）。金额在数据库中以整数「分」存储，避免浮点计算误差。密码使用带随机盐的 scrypt 散列；会话令牌随机生成，服务端只保存令牌散列，并在每次访问账本或写入时核对用户身份。

## 1. 在 PyCharm 中打开

用 PyCharm 打开本 `python-ledger` 文件夹（即包含 `requirements.txt` 的文件夹）。进入 **Settings → Project: python-ledger → Python Interpreter → Add Interpreter → Add Local Interpreter → Existing**，选择本项目的：

```text
<本文件夹>\.venv\Scripts\python.exe
```

当前交付目录内已创建独立 `.venv` 并安装依赖；不要选择旧项目 `first\.venv` 作为此项目解释器。如果复制项目时不包含 `.venv`，按下一节重建即可。

## 2. 首次安装或重建环境（Windows PowerShell）

在本文件夹的终端运行：

```powershell
& 'C:\Users\79327\AppData\Local\Programs\Python\Python312\python.exe' -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

若基础 Python 的位置变化，可将第一行路径替换为本机 Python 3.12 的路径。所有包装入此文件夹的 `.venv`，不会改动其他项目环境。

## 3. 启动并使用

在本文件夹的终端运行：

```powershell
& .\.venv\Scripts\python.exe -m uvicorn ledger.app:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000>，先注册账号，然后录入账目。数据默认固定保存在本项目根目录的 `ledger.db`，与启动时的工作目录无关；重启服务后仍在。可通过环境变量 `LEDGER_DB` 指定其他数据库路径。请备份此数据库文件以保存账目；不要把它提交到 Git。停止服务按 `Ctrl+C`。

如需在 Python 脚本中查看注册的用户名，在本文件夹运行 `& .\.venv\Scripts\python.exe .\list_users.py`，或在 PyCharm 中运行 `list_users.py`。脚本会显示实际查询的数据库路径，不会创建空数据库；密码原文无法查询。

PyCharm 也可以添加 **Python** 运行配置：Module name 设为 `uvicorn`，Parameters 设为 `ledger.app:app --host 127.0.0.1 --port 8000`，Working directory 设为本文件夹，Interpreter 选择上述 `.venv`。

## 4. 运行测试

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

测试覆盖密码散列与登录/退出、未经登录拒绝写入、不同用户的账目隔离、重启后的账目持久化，以及无效金额和备注的拒绝。

## 本地与云端的区别

当前命令只监听本机 `127.0.0.1`，其他设备或互联网无法直接访问。数据库和账号只存在于本机的 `ledger.db`，与原网站的账号及账目不互通。此版本没有自动发布、同步或云备份。未来要提供公网访问，需要单独选择托管服务、持久化存储、HTTPS、数据库备份，并调整生产环境的会话 Cookie 和安全配置；不能简单把当前本地启动命令暴露到公网。
