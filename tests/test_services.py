import json

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from config import get_settings
from services.github import GitHubClient, SubmissionUnknown
from services.ollama import OllamaClient


@pytest.fixture
def github_settings(monkeypatch):
    settings = get_settings().model_copy(
        update={
            "github_owner": "example",
            "github_repo": "project",
            "github_token": SecretStr("test-private-token"),
        }
    )
    monkeypatch.setattr("services.github.get_settings", lambda: settings)


def transport(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_github_post_timeout_is_ambiguous_and_not_retried(monkeypatch, github_settings):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)

    transport(monkeypatch, handler)
    with pytest.raises(SubmissionUnknown):
        GitHubClient().start("aurora.yml", "main", "request-123")
    assert len(calls) == 1
    assert calls[0].url.path.endswith("/workflows/aurora.yml/dispatches")
    assert json.loads(calls[0].content)["inputs"]["portal_request_id"] == "request-123"


def test_dispatch_supports_current_and_legacy_responses(monkeypatch, github_settings):
    responses = [
        httpx.Response(200, json={"workflow_run_id": 98765432100}),
        httpx.Response(204),
    ]
    transport(monkeypatch, lambda request: responses.pop(0))
    assert GitHubClient().start("portal.yml", "main", "a")["id"] == 98765432100
    assert GitHubClient().start("portal.yml", "main", "b")["id"] is None


def test_discovery_matches_exact_request_id(monkeypatch, github_settings):
    transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "workflow_runs": [
                    {"id": 1, "display_title": "NIRS another-request"},
                    {"id": 2, "display_title": "NIRS request-123"},
                ]
            },
        ),
    )
    assert GitHubClient().find_run("portal.yml", "main", "request-123") == 2
    assert GitHubClient().find_run("portal.yml", "main", "absent") is None


def test_artifact_redirect_does_not_forward_token(monkeypatch, github_settings):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/artifacts/9"):
            return httpx.Response(
                200,
                json={
                    "workflow_run": {"id": 10},
                    "size_in_bytes": 10,
                    "expired": False,
                },
            )
        if request.url.host == "api.github.com":
            assert "authorization" in request.headers
            return httpx.Response(
                302,
                headers={
                    "location": "https://example.blob.core.windows.net/artifact?sig=test"
                },
            )
        assert "authorization" not in request.headers
        return httpx.Response(
            200, content=b"PK-archive", headers={"content-type": "application/zip"}
        )

    transport(monkeypatch, handler)
    assert b"".join(GitHubClient().download(10, "9")) == b"PK-archive"
    assert len(calls) == 3


def test_artifact_rejects_untrusted_redirect(monkeypatch, github_settings):
    def handler(request):
        if request.url.path.endswith("/artifacts/9"):
            return httpx.Response(200, json={"workflow_run": {"id": 10}})
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    transport(monkeypatch, handler)
    with pytest.raises(HTTPException) as exc:
        b"".join(GitHubClient().download(10, "9"))
    assert exc.value.status_code == 502


def test_artifact_checks_owner_run_and_expiry(monkeypatch, github_settings):
    response = {"workflow_run": {"id": 99}, "expired": False}
    transport(monkeypatch, lambda request: httpx.Response(200, json=response))
    with pytest.raises(HTTPException) as exc:
        b"".join(GitHubClient().download(10, "9"))
    assert exc.value.status_code == 502
    response.update(workflow_run={"id": 10}, expired=True)
    with pytest.raises(HTTPException) as exc:
        b"".join(GitHubClient().download(10, "9"))
    assert exc.value.status_code == 410


def test_ollama_response(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"message": {"content": "Ответ модели"}})

    transport(monkeypatch, handler)
    assert (
        OllamaClient().generate([{"role": "user", "content": "hello"}])
        == "Ответ модели"
    )
    assert b'"think":false' in requests[0].content
    assert b'"num_ctx":4096' in requests[0].content


def test_ollama_timeout_releases_generation_slot(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout("slow model", request=request)

    transport(monkeypatch, timeout)
    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            OllamaClient().generate([{"role": "user", "content": "hello"}])
        assert exc.value.status_code == 504
