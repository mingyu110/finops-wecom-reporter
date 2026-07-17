# tests/test_wecom_adapter_handler.py
import json
import pytest
from src.wecom_adapter.handler import handle


class FakeWeCom:
    def __init__(self):
        self.markdowns = []
        self.uploads = []
        self.files = []

    def send_markdown(self, content):
        self.markdowns.append(content)
        return {"errcode": 0}

    def upload_media(self, file_bytes, filename):
        self.uploads.append((file_bytes, filename))
        return "MID-1"

    def send_file(self, media_id):
        self.files.append(media_id)
        return {"errcode": 0}


class FakeS3:
    def __init__(self, content):
        self._content = content
        self.gets = []

    def get_object(self, **kwargs):
        self.gets.append(kwargs)
        return {"Body": _Body(self._content)}


class _Body:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


def _sqs_event(message_body):
    return {"Records": [{"body": json.dumps(message_body, ensure_ascii=False)}]}


def test_handle_pushes_markdown_and_file():
    msg = {
        "schemaVersion": "1",
        "summaryMarkdown": "## 月报\n$511.09",
        "artifact": {"bucket": "b", "key": "reports/x.html",
                     "fileName": "x.html", "contentType": "text/html"},
    }
    wecom, s3 = FakeWeCom(), FakeS3(b"<html>r</html>")
    result = handle(_sqs_event(msg), None, wecom=wecom, s3=s3, env={})

    assert "511.09" in wecom.markdowns[0]
    assert "完整报告见附件" in wecom.markdowns[0]
    assert s3.gets[0] == {"Bucket": "b", "Key": "reports/x.html"}
    assert wecom.uploads[0] == (b"<html>r</html>", "x.html")
    assert wecom.files == ["MID-1"]
    assert result["processed"] == 1


def test_handle_markdown_only_when_no_artifact():
    msg = {"summaryMarkdown": "只有摘要", "artifact": None}
    wecom, s3 = FakeWeCom(), FakeS3(b"")
    handle(_sqs_event(msg), None, wecom=wecom, s3=s3, env={})
    assert wecom.markdowns == ["只有摘要"]
    assert wecom.uploads == []
    assert wecom.files == []
    assert s3.gets == []


def test_handle_propagates_error_for_retry():
    class FailingWeCom(FakeWeCom):
        def send_markdown(self, content):
            raise RuntimeError("push failed")

    msg = {"summaryMarkdown": "x", "artifact": None}
    with pytest.raises(RuntimeError):
        handle(_sqs_event(msg), None, wecom=FailingWeCom(), s3=FakeS3(b""), env={})
