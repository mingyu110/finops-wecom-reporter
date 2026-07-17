# tests/conftest.py
import pytest


@pytest.fixture(autouse=True)
def placeholder_aws_env(monkeypatch):
    """Feed botocore's default credential chain obviously-fake, test-only values.
    These are NOT credential-shaped: no AKIA prefix, not named 'secret'/'token'."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing-only-not-a-real-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing-only-not-a-real-value")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing-only-session")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
