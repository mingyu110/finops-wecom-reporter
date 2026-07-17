# tests/test_wecom_client.py
import json
import urllib.error
import pytest
from src.wecom_client import client as wecom_client
from src.wecom_client.client import (
    WeComClient,
    WeComApiError,
    WeComTransportError,
    _default_http,
)


def make_client(responses):
    calls = []

    def http(url, data, headers):
        calls.append({"url": url, "data": data, "headers": headers})
        return responses.pop(0)

    c = WeComClient("KEY-123", http=http)
    c._calls = calls
    return c


def test_send_markdown_posts_correct_payload():
    c = make_client([{"errcode": 0, "errmsg": "ok"}])
    c.send_markdown("## hi")
    sent = c._calls[0]
    assert "send?key=KEY-123" in sent["url"]
    payload = json.loads(sent["data"])
    assert payload["msgtype"] == "markdown"
    assert payload["markdown"]["content"] == "## hi"


def test_send_markdown_raises_on_errcode():
    c = make_client([{"errcode": 93000, "errmsg": "invalid webhook"}])
    with pytest.raises(WeComApiError) as ei:
        c.send_markdown("x")
    assert ei.value.errcode == 93000


def test_upload_media_returns_media_id():
    c = make_client([{"errcode": 0, "errmsg": "ok", "media_id": "MID-9"}])
    mid = c.upload_media(b"filedata", "report.html")
    assert mid == "MID-9"
    sent = c._calls[0]
    assert "upload_media?key=KEY-123&type=file" in sent["url"]
    # multipart body carries filename and bytes
    assert b"report.html" in sent["data"]
    assert b"filedata" in sent["data"]
    assert "multipart/form-data" in sent["headers"]["Content-Type"]


def test_send_file_posts_media_id():
    c = make_client([{"errcode": 0, "errmsg": "ok"}])
    c.send_file("MID-9")
    payload = json.loads(c._calls[0]["data"])
    assert payload["msgtype"] == "file"
    assert payload["file"]["media_id"] == "MID-9"


def test_default_http_error_never_leaks_key(monkeypatch):
    # The webhook key rides in the request URL query string. urllib's HTTPError
    # str/url embeds that full URL; _default_http must NOT let it surface.
    secret_url = (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SECRET-KEY-XYZ"
    )

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(
            url=secret_url, code=500, msg="Internal Server Error",
            hdrs=None, fp=None,
        )

    monkeypatch.setattr(wecom_client.urllib.request, "urlopen", boom)
    with pytest.raises(WeComTransportError) as ei:
        _default_http(secret_url, b"{}", {"Content-Type": "application/json"})
    msg = str(ei.value)
    assert "SECRET-KEY-XYZ" not in msg
    assert "key=" not in msg
    assert secret_url not in msg
    assert "500" in msg  # status code is preserved for diagnosis
