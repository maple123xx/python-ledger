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

## 5. 临时公网访问：Cloudflare Tunnel（Windows）

Cloudflare 是服务名称，安装的命令行工具叫 **`cloudflared`**（末尾有 `d`）。通过 Quick Tunnel，可以用一个临时 HTTPS 地址访问本机的记账程序，无需先把代码推送到 GitHub，也无需购买域名。这种方式适合临时测试；程序和数据库仍在自己的电脑上。

### 5.1 下载并安装 cloudflared（首次使用）

在 PowerShell 中运行：

```powershell
winget install --id Cloudflare.cloudflared --exact
```

安装后重新打开 PowerShell。如果使用 PyCharm 终端，建议完全退出并重新打开 PyCharm，以便加载更新后的 PATH。检查安装结果：

```powershell
cloudflared --version
```

如果电脑没有 `winget`，打开 [Cloudflare 官方下载页](https://developers.cloudflare.com/tunnel/downloads/)，在 Windows 区域选择与电脑架构对应的版本。常见的 64 位 Intel/AMD Windows 可下载 64-bit MSI 安装包，或下载 `cloudflared-windows-amd64.exe` 直接运行。

手动下载 EXE 后，下面以文件位于 `C:\tools\cloudflared-windows-amd64.exe` 为例；请替换成自己实际保存的位置：

```powershell
& 'C:\tools\cloudflared-windows-amd64.exe' --version
```

Windows 上的 cloudflared 不会自动更新。通过 winget 安装的版本可以运行 `winget upgrade --id Cloudflare.cloudflared --exact` 更新；手动下载的版本可从官方下载页重新下载。

### 5.2 第一个终端：启动记账服务

在 PyCharm 中打开项目根目录的终端（当前文件夹应包含 `requirements.txt` 和 `.venv`），运行：

```powershell
& .\.venv\Scripts\python.exe -m uvicorn ledger.app:app --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 后，先在浏览器打开 <http://127.0.0.1:8000>，确认登录页面或账本可以正常使用。**保持这个终端运行，不要关闭，也不要按 Ctrl+C。** 如果服务已经启动且本地页面正常，无需重复启动。

### 5.3 第二个终端：启动公网隧道

在 PyCharm 的 Terminal 面板点击 `+` 新开一个终端，或另外打开 PowerShell，运行：

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

如果使用手动下载的 EXE，则改用实际文件路径，例如：

```powershell
& 'C:\tools\cloudflared-windows-amd64.exe' tunnel --url http://127.0.0.1:8000
```

等待终端输出类似 `https://随机名称.trycloudflare.com` 的网址，复制**本次实际生成的完整地址**到浏览器即可访问，也可以用手机移动网络验证。这个公网地址提供 HTTPS，但隧道连接本机服务时仍使用上面命令中的 `http://127.0.0.1:8000`。

两个终端需要同时保持运行：第一个运行 Uvicorn，第二个运行 cloudflared。电脑关机、休眠、断网或任一程序停止，都会导致公网访问中断。重启 Quick Tunnel 后通常会生成新的地址，要使用最新输出的网址。

### 5.4 常见问题

**提示“无法将 cloudflared 识别为 cmdlet……”**

先按 5.1 安装并重新打开终端。如果仍找不到命令，使用 cloudflared 可执行文件的完整路径。可以在文件资源管理器中找到安装的 EXE 后复制其路径。安装路径可能因安装方式而不同，不要直接假定它位于某个 Program Files 文件夹。

**公网显示 Bad Gateway / 502**

通常表示隧道连不到本机的记账服务。按顺序检查：

1. 先打开 <http://127.0.0.1:8000>。如果本地也打不开，检查第一个终端的错误信息，并按 5.2 启动 Uvicorn。
2. 确认隧道使用 `--url http://127.0.0.1:8000`，端口与 Uvicorn 一致；本项目的默认本地服务不是 HTTPS。
3. 本地页面正常后，检查第二个终端的日志，并刷新当前隧道的公网地址。必要时在第二个终端按 `Ctrl+C` 停止隧道，再运行 5.3 的命令，使用新地址。

**停止公网访问**

在运行 cloudflared 的第二个终端按 `Ctrl+C` 即可停止隧道，本地记账服务仍可继续使用。若也要停止本地服务，再到第一个终端按 `Ctrl+C`。

更多说明见 [Cloudflare Quick Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)。Quick Tunnel 面向开发测试，不保证持续可用；长期运行应使用正式部署方案。

## 本地、临时隧道与云端部署的区别

仅启动 Uvicorn 时，本项目监听本机 `127.0.0.1`，其他设备无法直接访问。启动上述隧道后，公网请求经 Cloudflare 转发到本机，但账号和账目仍保存于本机 `ledger.db`；通过公网录入的账目也会写入这份数据库，与原 JavaScript 网站的账号及账目不互通。

隧道不会把程序部署到云服务器，也不会自动同步或备份数据库。正式云端部署需要持久化存储、HTTPS 和数据库备份，并完善生产环境的安全 Cookie、CSRF 防护及登录限流。当前版本的隧道流程用于临时测试，长期公开前需完成这些调整。
