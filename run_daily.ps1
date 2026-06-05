# A股每日复盘 - Windows 本地运行脚本
# 每天收盘后双击此文件即可运行，或在任务计划程序中调用

Write-Host @"
╔══════════════════════════════════════════════════════╗
║        📊 A股每日复盘系统 - 本地运行脚本              ║
╚══════════════════════════════════════════════════════╝
"@

# ============================================================
# 🔧 配置区 - 按你的实际情况修改以下内容
# ============================================================

# 通达信 vipdoc 路径（如果安装了通达信，设置此路径可以获取更全的数据）
$env:TDX_VIPDOC_PATH = ""

# 邮箱配置（如需发送邮件报告，填写以下信息）
# QQ邮箱授权码获取：QQ邮箱 → 设置 → 账户 → POP3/SMTP服务 → 生成授权码
$env:SMTP_HOST = "smtp.qq.com"
$env:SMTP_PORT = "587"
$env:SMTP_USER = ""
$env:SMTP_PASS = ""      # 授权码，不是QQ密码！
$env:TO_EMAILS = ""

# ============================================================
# 以下为运行逻辑，一般不需要修改
# ============================================================

# 切换到项目目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 检查 Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "🐍 $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 未找到 Python，请先安装 Python 3.9+ " -ForegroundColor Red
    Write-Host "   下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

# 检查依赖
Write-Host "📦 检查依赖..."
$deps = python -c "import akshare, pandas; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ 依赖缺失，正在安装..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# 运行复盘
Write-Host ""
Write-Host "🚀 开始获取数据并生成报告..." -ForegroundColor Cyan
Write-Host ""

python scripts/main.py

# 显示结果
Write-Host ""
if (Test-Path "docs/index.html") {
    $reportTime = (Get-Item "docs/index.html").LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "✅ 报告已生成: docs/index.html (生成时间: $reportTime)" -ForegroundColor Green
    Write-Host ""
    Write-Host "📂 是否用浏览器打开报告？(Y/n)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq "" -or $response -eq "y" -or $response -eq "Y") {
        Start-Process "docs/index.html"
    }
} else {
    Write-Host "❌ 报告生成失败，请检查上方错误信息" -ForegroundColor Red
}

Write-Host ""
Read-Host "按回车键退出"
