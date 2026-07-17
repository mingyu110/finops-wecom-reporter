# src/finops_client/client.py
import hashlib
import json
import urllib.request
import urllib.error

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import botocore.session

ENDPOINT_TEMPLATE = "https://finops-agent.{region}.api.aws"
SERVICE_NAME = "finops-agent"


class FinOpsApiError(Exception):
    def __init__(self, status, body):
        self.status = status
        self.body = body if isinstance(body, str) else body.decode("utf-8", "replace")
        super().__init__(f"finops-agent API error {status}: {self.body}")


def _default_http_post(url, headers, body):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class FinOpsClient:
    def __init__(self, agent_space_id, region="us-east-1", *,
                 http_post=None, credentials=None):
        self.agent_space_id = agent_space_id
        self.region = region
        self.endpoint = ENDPOINT_TEMPLATE.format(region=region)
        self._http_post = http_post or _default_http_post
        if credentials is None:
            credentials = botocore.session.Session().get_credentials()
        self._credentials = credentials

    def call(self, operation, payload):
        url = f"{self.endpoint}/{operation}"
        body = json.dumps(payload).encode("utf-8")
        aws_req = AWSRequest(
            method="POST",
            url=url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Amz-Content-SHA256": hashlib.sha256(body).hexdigest(),
            },
        )
        SigV4Auth(self._credentials, SERVICE_NAME, self.region).add_auth(aws_req)
        headers = dict(aws_req.headers)
        status, resp_body = self._http_post(url, headers, body)
        if not (200 <= status < 300):
            raise FinOpsApiError(status, resp_body)
        if not resp_body:
            return {}
        return json.loads(resp_body)

    def create_task(self, prompt):
        resp = self.call("createTask", {
            "agentSpaceId": self.agent_space_id,
            "prompt": prompt,
        })
        # 响应把任务体包在 "task" 信封里（preview 服务）；兼容扁平结构。
        task = resp.get("task", resp)
        return task["taskId"]

    def get_task(self, task_id):
        resp = self.call("getTask", {
            "agentSpaceId": self.agent_space_id,
            "taskId": task_id,
        })
        # 解包 "task" 信封，使调用方直接拿到 status/output 等字段。
        return resp.get("task", resp)

    def list_artifacts(self):
        resp = self.call("listArtifacts", {"agentSpaceId": self.agent_space_id})
        return resp.get("artifacts", [])

    def get_artifact_content(self, artifact_id):
        # getArtifactContent 直接返回产物全文（HTML 内联，非 presigned URL）。
        # 走 call() 会 json.loads，故这里直接用低层 http_post 拿原始 bytes。
        url = f"{self.endpoint}/getArtifactContent"
        payload = json.dumps({
            "agentSpaceId": self.agent_space_id,
            "artifactId": artifact_id,
        }).encode("utf-8")
        aws_req = AWSRequest(method="POST", url=url, data=payload,
                             headers={
                                 "Content-Type": "application/json",
                                 "X-Amz-Content-SHA256": hashlib.sha256(payload).hexdigest(),
                             })
        SigV4Auth(self._credentials, SERVICE_NAME, self.region).add_auth(aws_req)
        status, resp_body = self._http_post(url, dict(aws_req.headers), payload)
        if not (200 <= status < 300):
            raise FinOpsApiError(status, resp_body)
        return resp_body
