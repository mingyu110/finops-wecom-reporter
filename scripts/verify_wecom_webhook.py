# scripts/verify_wecom_webhook.py
"""前置验证项 #2：实测企微群机器人 markdown + file 两条链路。
用法：WECOM_WEBHOOK_KEY=xxx python scripts/verify_wecom_webhook.py
webhook key 只从环境变量读，不接受也不打印其值。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.wecom_client.client import WeComClient, WeComApiError


def main():
    key = os.environ.get("WECOM_WEBHOOK_KEY")
    if not key:
        print("ERROR: set WECOM_WEBHOOK_KEY env var", file=sys.stderr)
        return 2
    client = WeComClient(key)
    try:
        client.send_markdown("## ✅ 连通性测试\n这是一条 FinOps Agent 集成的 markdown 测试消息。")
        print("markdown OK")
        sample = b"<html><body>connectivity test report</body></html>"
        media_id = client.upload_media(sample, "connectivity-test.html")
        print("upload_media OK, media_id acquired")
        client.send_file(media_id)
        print("send_file OK")
        print("ALL PASS — 前置验证项 #2 通过")
        return 0
    except WeComApiError as e:
        print(f"WeCom API error errcode={e.errcode} errmsg={e.errmsg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
