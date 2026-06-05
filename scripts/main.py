#!/usr/bin/env python3
"""
A股每日复盘 - 主入口
依次执行：数据获取 → 报告生成 → 邮件发送
"""

import sys
import os

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(__file__))

from fetch_data import collect_all_data
from generate_report import generate_html_report, generate_markdown_report
from send_email import send_report_email


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║        📊 A股每日复盘系统 v1.0                      ║
║        A-Stock Daily Review Bot                     ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # Step 1: 获取数据
    print("\n📡 Step 1/3: 获取市场数据...")
    print("-" * 50)
    data = collect_all_data()
    
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
        send_report_email()
    else:
        print("⚠️ 未配置邮箱（SMTP_USER 未设置），跳过邮件发送")
        print("💡 提示：设置环境变量后即可自动发送邮件：")
        print("   SMTP_USER=your@email.com")
        print("   SMTP_PASS=your_password")
        print("   TO_EMAILS=recipient@email.com")
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║  ✅ 复盘完成!                                       ║
║  📄 HTML 报告: {html_path}          ║
║  🌐 在线查看: 待 GitHub Pages 部署                  ║
╚══════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
