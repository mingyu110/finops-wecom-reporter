# src/orchestrator/handler.py
import json
import os

from src.finops_client.client import FinOpsClient
from src.orchestrator.report_source import CreateTaskReportSource


def handle(event, context, *, source=None, s3=None, sqs=None, env=None):
    env = env or os.environ
    prompt = env.get("REPORT_PROMPT", "生成成本报告")
    period = env.get("PERIOD", "monthly")
    bucket = env["ARTIFACT_BUCKET"]
    queue_url = env["REPORT_QUEUE_URL"]
    date = (event or {}).get("date", "latest")

    report = source.fetch(prompt)

    artifact_ref = None
    if report.artifact_bytes is not None:
        key = f"reports/{date}/{report.artifact_name}"
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=report.artifact_bytes,
            ContentType=report.artifact_content_type or "application/octet-stream",
        )
        artifact_ref = {
            "bucket": bucket,
            "key": key,
            "fileName": report.artifact_name,
            "contentType": report.artifact_content_type,
        }

    message = {
        "schemaVersion": "1",
        "period": period,
        "generatedAt": (event or {}).get("time", date),
        "summaryMarkdown": report.summary_markdown,
        "artifact": artifact_ref,
    }
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message, ensure_ascii=False))
    return {"status": "sent"}


def lambda_handler(event, context):
    import boto3
    env = os.environ
    client = FinOpsClient(agent_space_id=env["AGENT_SPACE_ID"],
                          region=env.get("REGION", "us-east-1"))
    source = CreateTaskReportSource(client)
    return handle(event, context,
                  source=source,
                  s3=boto3.client("s3"),
                  sqs=boto3.client("sqs"),
                  env=env)
