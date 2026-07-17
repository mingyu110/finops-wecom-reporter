# src/wecom_adapter/handler.py
import json
import os

from src.wecom_adapter.renderer import render_markdown
from src.wecom_client.client import WeComClient


def handle(event, context, *, wecom=None, s3=None, env=None):
    env = env or os.environ
    records = (event or {}).get("Records", [])
    for record in records:
        msg = json.loads(record["body"])
        artifact = msg.get("artifact")
        has_attachment = artifact is not None
        markdown = render_markdown(msg.get("summaryMarkdown", ""),
                                   has_attachment=has_attachment)
        wecom.send_markdown(markdown)
        if has_attachment:
            obj = s3.get_object(Bucket=artifact["bucket"], Key=artifact["key"])
            file_bytes = obj["Body"].read()
            media_id = wecom.upload_media(file_bytes, artifact["fileName"])
            wecom.send_file(media_id)
    return {"processed": len(records)}


def _load_webhook_key(env):
    import boto3
    secret_arn = env["WECOM_SECRET_ARN"]
    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=secret_arn)
    secret = json.loads(resp["SecretString"])
    return secret["webhookKey"]


def lambda_handler(event, context):
    import boto3
    env = os.environ
    wecom = WeComClient(_load_webhook_key(env))
    return handle(event, context, wecom=wecom, s3=boto3.client("s3"), env=env)
