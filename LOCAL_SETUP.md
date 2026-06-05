# A股每日复盘系统 - 本地部署指南

## 📋 概述

A股每日复盘系统现已在本地电脑上运行，不再依赖 GitHub Actions 自动推送。

每天收盘后运行一次，即可生成当日复盘 HTML 报告。

---

## 🖥️ 环境要求

- **操作系统**: Windows 10/11（macOS/Linux 也可）
- **Python**: 3.9 或以上（推荐 3.11）
- **网络**: 需要能访问新浪财经 / 东方财富
- **可选**: 通达信软件（有本地数据文件的话，数据更全更快）

---

## 📦 第一步：下载项目

打开 PowerShell，执行：

```powershell
# 克隆项目到本地
cd ~
git clone https://github.com/dgguasa6622/a-stock-daily-review.git
cd a-stock-daily-review
```

如果还没安装 Git，先去 https://git-scm.com/download/win 下载安装。

---

## 🐍 第二步：安装 Python 依赖

```powershell
# 安装依赖
pip install -r requirements.txt
```

如果 pip 报错，试试：
```powershell
python -m pip install -r requirements.txt
```

---

## 📂 第三步：配置通达信数据（可选但推荐）

如果你电脑上装了通达信，可以设置本地数据路径，数据获取会更快更全：

```powershell
# 设置通达信 vipdoc 目录路径（根据你实际的安装路径修改）
$env:TDX_VIPDOC_PATH = "C:\new_tdx\vipdoc"
```

常见通达信安装路径：
- `C:\new_tdx\vipdoc`
- `C:\通达信\vipdoc`
- `D:\new_tdx\vipdoc`

如果系统能自动检测到，就不需要手动设置。

---

## 🚀 第四步：运行复盘

```powershell
# 进入项目目录
cd ~/a-stock-daily-review

# 运行复盘
python scripts/main.py
```

运行完成后，会在 `docs/` 目录下生成 HTML 报告，用浏览器打开即可查看：

```powershell
# 打开最新报告
start docs/index.html
```

---

## 📧 第五步（可选）：配置邮件发送

如果要自动发送邮件报告到 QQ 邮箱：

```powershell
$env:SMTP_HOST = "smtp.qq.com"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "17598181@qq.com"
$env:SMTP_PASS = "你的QQ邮箱授权码"    # 不是QQ密码！是SMTP授权码
$env:TO_EMAILS = "17598181@qq.com"
```

QQ 邮箱授权码获取方式：
1. 登录 QQ 邮箱 → 设置 → 账户
2. 找到「POP3/IMAP/SMTP 服务」
3. 开启服务，按提示获取授权码

---

## ⏰ 第六步：设置 Windows 定时任务（每日自动运行）

### 方法一：Windows 任务计划程序（推荐）

1. 按 `Win + R`，输入 `taskschd.msc`，打开任务计划程序
2. 点击「创建基本任务」
3. 名称：`A股每日复盘`
4. 触发器：`每天`，时间设为 `17:30`
5. 操作：`启动程序`
   - 程序：`powershell.exe`
   - 参数：
     ```
     -NoProfile -WindowStyle Hidden -Command "cd ~/a-stock-daily-review; python scripts/main.py"
     ```
6. 点击完成

### 方法二：使用 PowerShell 脚本

创建文件 `run_daily.ps1`：

```powershell
# 设置环境变量（按需修改）
$env:TDX_VIPDOC_PATH = "C:\new_tdx\vipdoc"
$env:SMTP_USER = "17598181@qq.com"
$env:SMTP_PASS = "你的授权码"
$env:TO_EMAILS = "17598181@qq.com"

# 运行复盘
Set-Location ~/a-stock-daily-review
python scripts/main.py
```

然后在任务计划程序中执行这个脚本。

---

## 🔄 更新代码

当项目有更新时，拉取最新代码：

```powershell
cd ~/a-stock-daily-review
git pull origin main
```

---

## 📊 报告文件说明

- **HTML 报告**: `docs/index.html` — 用浏览器打开即可查看
- **Markdown 报告**: 在运行日志中输出，也可以手动保存

---

## ❓ 常见问题

| 问题 | 解决方法 |
|------|----------|
| 提示找不到 akhare | 运行 `pip install -r requirements.txt` |
| 数据全是空的 | 可能是非交易日，或者收盘后数据还没更新，稍等 10 分钟再试 |
| 通达信数据读不到 | 检查 `TDX_VIPDOC_PATH` 路径是否正确，通达信是否正常登录过 |
| 邮件发不出去 | 确认是「授权码」不是 QQ 密码；确认 SMTP 服务已开启 |
| pip 安装报错 | 试试 `python -m pip install --upgrade pip` 先升级 pip |

---

## 🏠 关于 GitHub Pages 网站

GitHub 上的网页版报告（`https://dgguasa6622.github.io/a-stock-daily-review/`）**仍然保留**，但不会再自动更新。

如果你想手动更新网页版，可以在 GitHub 仓库页面的 Actions 标签中手动触发一次运行。

---

## 📝 项目结构

```
a-stock-daily-review/
├── scripts/
│   ├── main.py            # 主入口
│   ├── fetch_data.py      # 数据获取
│   ├── data_sources.py    # 数据源（东方财富/新浪/通达信）
│   ├── generate_report.py # 报告生成
│   └── send_email.py      # 邮件发送
├── docs/                  # 生成的报告存放处
├── requirements.txt       # Python 依赖
└── LOCAL_SETUP.md         # 本文件
```
