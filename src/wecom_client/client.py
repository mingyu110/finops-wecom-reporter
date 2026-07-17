# src/wecom_client/client.py
import json
import urllib.error
import urllib.request

BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook"
_BOUNDARY = "----FinOpsWeComBoundary7MA4YWxkTrZu0gW"


class WeComApiError(Exception):
    def __init__(self, errcode, errmsg):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WeCom API error {errcode}: {errmsg}")


class WeComTransportError(Exception):
    """Raised on HTTP/transport failures.

    The message deliberately carries only an HTTP status code (when known) or a
    generic transport-failure note. It never includes the request URL, the
    original exception's string, or the webhook key, so the secret cannot leak
    into logs.
    """


def _default_http(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # e.code is the HTTP status; str(e)/e.url/e.filename may embed the URL
        # (and thus the webhook key), so do NOT chain or reuse the original.
        raise WeComTransportError(
            f"WeCom request failed with HTTP status {e.code}"
        ) from None
    except urllib.error.URLError:
        # e.reason / str(e) can also reference the request URL; keep it generic.
        raise WeComTransportError(
            "WeCom request failed: transport error"
        ) from None


class WeComClient:
    def __init__(self, webhook_key, *, http=None):
        self._key = webhook_key
        self._http = http or _default_http

    def _check(self, resp):
        if resp.get("errcode", 0) != 0:
            raise WeComApiError(resp.get("errcode"), resp.get("errmsg", ""))
        return resp

    def _post_json(self, url, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        return self._check(self._http(url, data, headers))

    def send_markdown(self, content):
        url = f"{BASE}/send?key={self._key}"
        return self._post_json(url, {"msgtype": "markdown",
                                     "markdown": {"content": content}})

    def send_file(self, media_id):
        url = f"{BASE}/send?key={self._key}"
        return self._post_json(url, {"msgtype": "file",
                                     "file": {"media_id": media_id}})

    def upload_media(self, file_bytes, filename):
        url = f"{BASE}/upload_media?key={self._key}&type=file"
        body = self._build_multipart(file_bytes, filename)
        headers = {"Content-Type": f"multipart/form-data; boundary={_BOUNDARY}"}
        resp = self._check(self._http(url, body, headers))
        return resp["media_id"]

    def _build_multipart(self, file_bytes, filename):
        pre = (
            f"--{_BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        post = f"\r\n--{_BOUNDARY}--\r\n".encode("utf-8")
        return pre + file_bytes + post
