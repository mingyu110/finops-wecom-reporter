# tests/test_finops_client.py
import json
from src.finops_client.client import FinOpsClient, FinOpsApiError


def make_client(responses):
    """responses: list of (status, body_bytes) popped per call."""
    calls = []

    def http_post(url, headers, body):
        calls.append({"url": url, "headers": headers, "body": body})
        return responses.pop(0)

    client = FinOpsClient(
        agent_space_id="space-123",
        http_post=http_post,
    )
    client._calls = calls
    return client


def test_call_signs_and_posts_to_operation_path():
    client = make_client([(200, b'{"ok": true}')])
    result = client.call("listArtifacts", {"agentSpaceId": "space-123"})
    assert result == {"ok": True}
    sent = client._calls[0]
    assert sent["url"] == "https://finops-agent.us-east-1.api.aws/listArtifacts"
    # SigV4 headers present
    assert "Authorization" in sent["headers"]
    assert sent["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256")
    assert "X-Amz-Content-SHA256" in sent["headers"] or "x-amz-content-sha256" in sent["headers"]
    # NO RPC target header
    assert "X-Amz-Target" not in sent["headers"]
    assert sent["headers"]["Content-Type"] == "application/json"


def test_call_raises_on_non_2xx():
    client = make_client([(400, b'{"message": "bad"}')])
    try:
        client.call("createTask", {"agentSpaceId": "space-123"})
        assert False, "should have raised"
    except FinOpsApiError as e:
        assert e.status == 400
        assert "bad" in e.body


def test_create_task_returns_task_id():
    client = make_client([(202, b'{"taskId": "t-999", "status": "PENDING"}')])
    task_id = client.create_task("给我6月成本报告")
    assert task_id == "t-999"
    body = json.loads(client._calls[0]["body"])
    assert body["agentSpaceId"] == "space-123"
    assert body["prompt"] == "给我6月成本报告"


def test_get_artifact_content_returns_raw_bytes():
    client = make_client([(200, b"<html>report</html>")])
    content = client.get_artifact_content("art-1")
    assert content == b"<html>report</html>"
