# tests/test_orchestrator_handler.py
import json
from src.orchestrator.handler import handle
from src.orchestrator.report_source import Report


class FakeSource:
    def __init__(self, report):
        self._report = report
        self.prompt = None

    def fetch(self, prompt):
        self.prompt = prompt
        return self._report


class FakeS3:
    def __init__(self):
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)


class FakeSQS:
    def __init__(self):
        self.sent = []

    def send_message(self, **kwargs):
        self.sent.append(kwargs)


ENV = {
    "ARTIFACT_BUCKET": "bucket-x",
    "REPORT_QUEUE_URL": "https://sqs/queue-x",
    "REPORT_PROMPT": "生成月度成本报告",
    "PERIOD": "monthly",
}


def test_handle_writes_artifact_to_s3_and_sends_sqs():
    report = Report(
        summary_markdown="## 月报\n总花费 $511.09",
        artifact_bytes=b"<html>r</html>",
        artifact_name="cost-overview-june-2026.html",
        artifact_content_type="text/html",
    )
    src, s3, sqs = FakeSource(report), FakeS3(), FakeSQS()
    result = handle({"date": "2026-07-15"}, None,
                    source=src, s3=s3, sqs=sqs, env=ENV)

    assert src.prompt == "生成月度成本报告"
    # S3 write
    put = s3.puts[0]
    assert put["Bucket"] == "bucket-x"
    assert put["Key"] == "reports/2026-07-15/cost-overview-june-2026.html"
    assert put["Body"] == b"<html>r</html>"
    assert put["ContentType"] == "text/html"
    # SQS message contract
    body = json.loads(sqs.sent[0]["MessageBody"])
    assert body["schemaVersion"] == "1"
    assert body["period"] == "monthly"
    assert "511.09" in body["summaryMarkdown"]
    assert body["artifact"]["bucket"] == "bucket-x"
    assert body["artifact"]["key"] == "reports/2026-07-15/cost-overview-june-2026.html"
    assert body["artifact"]["fileName"] == "cost-overview-june-2026.html"
    assert body["artifact"]["contentType"] == "text/html"
    assert result["status"] == "sent"


def test_handle_without_artifact_sends_null_artifact():
    report = Report(summary_markdown="只有摘要")
    src, s3, sqs = FakeSource(report), FakeS3(), FakeSQS()
    handle({}, None, source=src, s3=s3, sqs=sqs, env=ENV)
    assert s3.puts == []
    body = json.loads(sqs.sent[0]["MessageBody"])
    assert body["artifact"] is None
    assert body["summaryMarkdown"] == "只有摘要"
