# tests/test_report_source.py
import json
import pytest
from src.orchestrator.report_source import (
    CreateTaskReportSource, Report, ReportGenerationError,
)


class FakeClient:
    def __init__(self, task_states, output_text, artifacts, content):
        self._task_states = task_states  # list of status strings, popped per get_task
        self._output_text = output_text
        self._artifacts = artifacts
        self._content = content
        self.created_prompt = None

    def create_task(self, prompt):
        self.created_prompt = prompt
        return "task-1"

    def get_task(self, task_id):
        status = self._task_states.pop(0)
        task = {"taskId": task_id, "status": status}
        if status == "COMPLETED":
            task["output"] = {"text": self._output_text}
        return task

    def list_artifacts(self):
        return self._artifacts

    def get_artifact_content(self, artifact_id):
        return self._content[artifact_id]


def test_fetch_polls_until_completed_and_returns_report():
    output_text = json.dumps({
        "text": "## 6月成本\n总花费 $511.09",
        "artifactIds": ["art-1"],
    })
    client = FakeClient(
        task_states=["PENDING", "IN_PROGRESS", "COMPLETED"],
        output_text=output_text,
        artifacts=[{"artifactId": "art-1", "name": "cost.html",
                    "contentType": "text/html", "fileSize": 100}],
        content={"art-1": b"<html>report</html>"},
    )
    src = CreateTaskReportSource(client, poll_interval=0, sleep=lambda s: None)
    report = src.fetch("给我6月成本报告")

    assert isinstance(report, Report)
    assert client.created_prompt == "给我6月成本报告"
    assert "511.09" in report.summary_markdown
    assert report.artifact_bytes == b"<html>report</html>"
    assert report.artifact_name == "cost.html"
    assert report.artifact_content_type == "text/html"


def test_fetch_raises_on_failed_status():
    client = FakeClient(["FAILED"], "", [], {})
    src = CreateTaskReportSource(client, poll_interval=0, sleep=lambda s: None)
    with pytest.raises(ReportGenerationError):
        src.fetch("x")


def test_fetch_raises_on_poll_timeout():
    client = FakeClient(["PENDING", "PENDING"], "", [], {})
    src = CreateTaskReportSource(client, poll_interval=0, max_polls=2,
                                 sleep=lambda s: None)
    with pytest.raises(ReportGenerationError):
        src.fetch("x")


def test_fetch_without_artifacts_returns_markdown_only():
    output_text = json.dumps({"text": "只有摘要", "artifactIds": []})
    client = FakeClient(["COMPLETED"], output_text, [], {})
    src = CreateTaskReportSource(client, poll_interval=0, sleep=lambda s: None)
    report = src.fetch("x")
    assert report.summary_markdown == "只有摘要"
    assert report.artifact_bytes is None
    assert report.artifact_name is None
