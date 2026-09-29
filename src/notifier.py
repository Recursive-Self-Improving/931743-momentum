"""
通知模块
- 邮件通知（SMTP）
- 微信企业号/机器人
- 实时报警（风控触发时必须通知）
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Optional


class Notifier:
    """交易信号通知"""

    def __init__(self):
        self.smtp_host = os.environ.get('SMTP_HOST', '')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.smtp_user = os.environ.get('SMTP_USER', '')
        self.smtp_pass = os.environ.get('SMTP_PASS', '')
        self.to_email = os.environ.get('TO_EMAIL', '')
        self.wechat_webhook = os.environ.get('WECHAT_WEBHOOK', '')

    def _send_email(self, subject: str, body: str, is_html: bool = False) -> bool:
        """发送邮件"""
        if not all([self.smtp_host, self.smtp_user, self.smtp_pass, self.to_email]):
            print("⚠️ 邮件未配置，跳过")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = self.to_email
            msg['Subject'] = subject

            content_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            print(f"✅ 邮件发送成功: {subject}")
            return True
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")
            return False

    def _send_wechat(self, text: str) -> bool:
        """通过企业微信机器人发送"""
        if not self.wechat_webhook:
            print("⚠️ 微信webhook未配置，跳过")
            return False

        try:
            import requests
            payload = {
                "msgtype": "text",
                "text": {"content": text}
            }
            resp = requests.post(self.wechat_webhook, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"✅ 微信发送成功")
                return True
            else:
                print(f"❌ 微信发送失败: {resp.status_code}")
                return False
        except Exception as e:
            print(f"❌ 微信发送失败: {e}")
            return False

    def send_signal(self, decision: Dict, report: str, is_emergency: bool = False):
        """发送交易信号通知
        """
        now = datetime.now().strftime('%m-%d %H:%M')
        action = decision['action']

        if action == 'clear_all':
            subject = f"🚨[紧急清仓] ETF轮动策略 {now}"
            priority = True
        elif action == 'reduce_half':
            subject = f"⚠️[降仓预警] ETF轮动策略 {now}"
            priority = True
        elif action == 'rebalance':
            subject = f"🔄[调仓] ETF轮动策略 {now}"
            priority = False
        else:
            subject = f"📋[持仓] ETF轮动日报 {now}"
            priority = False

        # 仅在有交易动作、预警或强制通知时发送
        if priority or is_emergency:
            self._send_email(subject, report)
            self._send_wechat(report)
        else:
            print("💤 今日持仓不动，不发通知（可修改为每日都发）")

    def send_backtest_report(self, stats: Dict):
        """发送回测报告"""
        body = f"""
ETF动量轮动策略 回测报告

回测统计:
- 总收益率: {stats.get('total_return', 0):+.2f}%
- 年化收益: {stats.get('annual_return', 0):+.2f}%
- 最大回撤: {stats.get('max_drawdown', 0):+.2f}%
- 波动率: {stats.get('volatility', 0):.2f}%
- 夏普比: {stats.get('sharpe', 0):.2f}
- 日胜率: {stats.get('win_rate', 0):.1f}%
- 交易次数: {stats.get('trade_count', 0)}
- 最终资金: ¥{stats.get('final_value', 0):,.2f}
"""
        subject = f"📊 ETF轮动策略回测报告 {datetime.now().strftime('%Y-%m-%d')}"
        self._send_email(subject, body)

    def save_signal_to_file(self, report: str):
        """保存信号到本地，用于手动执行"""
        filename = f"~/a股动量轮动策略/logs/signal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filename = os.path.expanduser(filename)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 信号已保存到 {filename}")
        return filename
