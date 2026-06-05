#!/usr/bin/env python3
"""
A股每日复盘 - 邮件发送模块
通过 SMTP 发送复盘报告到指定邮箱
"""

import smtplib
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def load_config():
    """加载邮箱配置（从环境变量或配置文件）"""
    config = {
        "smtp_host": os.environ.get("SMTP_HOST", "smtp.qq.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        "smtp_user": os.environ.get("SMTP_USER", ""),
        "smtp_pass": os.environ.get("SMTP_PASS", ""),
        "to_emails": os.environ.get("TO_EMAILS", "").split(","),
        "use_ssl": os.environ.get("SMTP_SSL", "false").lower() == "true",
    }
    
    # 过滤空值
    config["to_emails"] = [e.strip() for e in config["to_emails"] if e.strip()]
    
    return config


def send_report_email():
    """发送复盘报告邮件"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    config = load_config()
    
    if not config["smtp_user"] or not config["smtp_pass"]:
        print("❌ 邮箱配置不完整，请设置环境变量 SMTP_USER 和 SMTP_PASS")
        return False
    
    if not config["to_emails"]:
        print("❌ 未设置收件人，请设置环境变量 TO_EMAILS")
        return False
    
    # 读取 Markdown 报告
    md_path = os.path.join(OUTPUT_DIR, "report.md")
    if not os.path.exists(md_path):
        print(f"❌ 报告文件不存在: {md_path}")
        return False
    
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # 构建邮件
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 A股每日复盘报告 - {today}"
    msg["From"] = config["smtp_user"]
    msg["To"] = ", ".join(config["to_emails"])
    
    # 纯文本版本（简单转换 Markdown）
    text_content = md_content.replace("#", "").replace("*", "").replace("|", " ").replace("`", "")
    
    # HTML 版本（从生成的 HTML 报告中提取）
    html_path = os.path.join(OUTPUT_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        # 简单 HTML 转换
        html_content = f"<html><body><pre>{md_content}</pre></body></html>"
    
    part1 = MIMEText(text_content, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)
    
    # 发送
    try:
        if config["use_ssl"]:
            server = smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"])
        else:
            server = smtplib.SMTP(config["smtp_host"], config["smtp_port"])
            server.starttls()
        
        server.login(config["smtp_user"], config["smtp_pass"])
        server.sendmail(config["smtp_user"], config["to_emails"], msg.as_string())
        server.quit()
        
        print(f"✅ 邮件已发送至: {', '.join(config['to_emails'])}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False


if __name__ == "__main__":
    send_report_email()
