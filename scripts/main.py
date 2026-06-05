#!/usr/bin/env python3
"""
A股每日复盘 - 主入口（本地版）
依次执行：数据获取 → 报告生成 → 邮件发送（可选）
"""

import sys
import os
from datetime import datetime

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(__file__))

from fetch_data import collect_all_data
from generate_report import generate_html_report, generate_markdown_report
from send_email import send_report_email


def check_tdx():
    """检测通达信本地数据是否可用"""
    from data_sources import tdx_is_available
    if tdx_is_available():
        tdx_path = os.environ.get("TDX_VIPDOC_PATH", "自动检测")
        print(f"   ✅ 通达信本地数据可用 (路径: {tdx_path})")
    else:
        print("   ⚠️ 未检测到通达信本地数据，将使用网络数据源")
        print("   💡 如需使用通达信数据，请设置环境变量 TDX_VIPDOC_PATH")
        print("     例如: $env:TDX_VIPDOC_PATH='C:\\new_tdx\\vipdoc'  (PowerShell)")


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║        📊 A股每日复盘系统 v2.0（本地版）             ║
║        A-Stock Daily Review - Local Edition          ║
╚══════════════════════════════════════════════════════╝
    """)
    
    today = datetime.now().strftime("%Y-%m-%d %A")
    print(f"📅 当前日期: {today}")
    print(f"🖥️  运行环境: 本地电脑\n")
    
    # 检测通达信数据
    check_tdx()
    print()
    
    # Step 1: 获取数据
    print("📡 Step 1/3: 获取市场数据...")
    print("-" * 50)
    try:
        data = collect_all_data()
    except Exception as e:
        print(f"\n❌ 数据获取失败: {e}")
        print("💡 常见原因：")
        print("   1. 网络连接问题")
        print("   2. 数据源暂时不可用（收盘后稍等片刻再试）")
        print("   3. 非交易日（周末/节假日）")
        sys.exit(1)
    
    # Step 2: 生成报告
    print(f"\n📝 Step 2/3: 生成复盘报告...")
    print("-" * 50)
    html_path = generate_html_report(data)
    md_content = generate_markdown_report(data)
    
    # Step 3: 发送邮件（如果配置了邮箱）
    print(f"\n📧 Step 3/3: 发送邮件...")
    print("-" * 50)
    
    smtp_user = os.environ.get("SMTP_USER", "")
    if smtp_user:
        try:
            send_report_email()
        except Exception as e:
            print(f"⚠️ 邮件发送失败: {e}")
    else:
        print("⚠️ 未配置邮箱（SMTP_USER 未设置），跳过邮件发送")
        print("💡 提示：设置环境变量后即可自动发送邮件：")
        print("   $env:SMTP_USER='your@email.com'           (PowerShell)")
        print("   $env:SMTP_PASS='your_authorization_code'   (PowerShell)")
        print("   $env:TO_EMAILS='recipient@email.com'       (PowerShell)")
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║  ✅ 复盘完成!                                       ║
║  📄 HTML 报告: {html_path}          ║
║  📂 用浏览器打开即可查看                             ║
╚══════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
