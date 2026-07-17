# src/orchestrator/report_source.py
import abc
import json
import time
from dataclasses import dataclass


@dataclass
class Report:
    summary_markdown: str
    artifact_bytes: bytes | None = None
    artifact_name: str | None = None
    artifact_content_type: str | None = None


class ReportGenerationError(Exception):
    pass


class FinOpsReportSource(abc.ABC):
    @abc.abstractmethod
    def fetch(self, prompt):
        ...


class CreateTaskReportSource(FinOpsReportSource):
    TERMINAL_OK = "COMPLETED"
    TERMINAL_FAIL = {"FAILED", "CANCELLED", "ERROR"}

    def __init__(self, client, *, poll_interval=15, max_polls=20, sleep=time.sleep):
        self._client = client
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._sleep = sleep

    def fetch(self, prompt):
        task_id = self._client.create_task(prompt)
        task = self._poll_until_done(task_id)
        summary_md, artifact_ids = self._parse_output(task)
        artifact_bytes = artifact_name = artifact_ct = None
        if artifact_ids:
            artifact_bytes, artifact_name, artifact_ct = self._fetch_artifact(
                artifact_ids[0])
        return Report(
            summary_markdown=summary_md,
            artifact_bytes=artifact_bytes,
            artifact_name=artifact_name,
            artifact_content_type=artifact_ct,
        )

    def _poll_until_done(self, task_id):
        for _ in range(self._max_polls):
            task = self._client.get_task(task_id)
            status = task.get("status")
            if status == self.TERMINAL_OK:
                return task
            if status in self.TERMINAL_FAIL:
                raise ReportGenerationError(f"task {task_id} ended {status}")
            self._sleep(self._poll_interval)
        raise ReportGenerationError(
            f"task {task_id} not done after {self._max_polls} polls")

    def _parse_output(self, task):
        # output.text 内层还是 JSON：{"text": <markdown>, "artifactIds": [...]}
        raw = task.get("output", {}).get("text", "")
        try:
            inner = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return (raw or ""), []
        return inner.get("text", ""), inner.get("artifactIds", [])

    def _fetch_artifact(self, artifact_id):
        meta = {}
        for a in self._client.list_artifacts():
            if a.get("artifactId") == artifact_id:
                meta = a
                break
        content = self._client.get_artifact_content(artifact_id)
        return content, meta.get("name"), meta.get("contentType")
