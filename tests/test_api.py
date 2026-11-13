from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

import main
from database import get_db
from models import Artifact, Chat, Job, Message, Pipeline, Run, User
from models.entities import AccessSession
from routers import auth
from services.github import SubmissionUnknown
from services.ollama import get_ollama


class TestModel:
    def generate(self, messages):
        assert messages[-1]["content"]
        return "Проверьте журнал компилятора."

    def available(self):
        return True


@pytest.fixture
def client(session):
    main.app.dependency_overrides[get_db] = lambda: session
    main.app.dependency_overrides[get_ollama] = TestModel
    auth._attempts.clear()
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()


def account(client, email="owner@example.com"):
    data = {"email": email, "password": "local-test-password"}
    assert client.post("/auth/register/send", json=data).status_code == 201
    response = client.post("/auth/send", json=data)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_authentication_logout_and_expiry(client, session):
    headers = account(client)
    assert client.get("/api/chats").status_code == 401
    assert client.get("/api/chats", headers=headers).status_code == 200
    stored = session.scalar(select(User))
    assert stored.password_hash.startswith("scrypt$")
    assert stored.password_hash != "local-test-password"
    token = session.scalar(select(AccessSession))
    assert token.token_hash not in headers["Authorization"]
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert client.get("/api/chats", headers=headers).status_code == 401
    headers = {
        "Authorization": "Bearer "
        + client.post(
            "/auth/send",
            json={"email": "owner@example.com", "password": "local-test-password"},
        ).json()["access_token"]
    }
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/chats", headers=headers).status_code == 401
    assert (
        client.post(
            "/auth/register/send",
            json={"email": "OWNER@example.com", "password": "local-test-password"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/auth/send",
            json={"email": "owner@example.com", "password": "wrong-password"},
        ).status_code
        == 401
    )


def test_chat_history_is_private_and_failed_generation_is_atomic(client, session):
    headers = account(client)
    other = account(client, "other@example.com")
    chat_id = client.post("/chats/new", json={}, headers=headers).json()["id"]
    url = f"/api/chats/{chat_id}"
    assert client.get(url, headers=other).status_code == 404
    assert (
        client.post(
            url + "/messages", headers=other, json={"content": "hello"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            url + "/messages", headers=headers, json={"content": "   "}
        ).status_code
        == 422
    )
    assert (
        client.post(
            url + "/messages", headers=headers, json={"content": "Ошибка сборки"}
        ).status_code
        == 200
    )
    history = client.get(url, headers=headers).json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert client.get("/api/chats?q=Ошибка", headers=headers).json()[0]["id"] == chat_id
    assert client.get("/api/chats", headers=other).json() == []

    class FailingModel(TestModel):
        def generate(self, messages):
            raise HTTPException(503, "Model unavailable")

    main.app.dependency_overrides[get_ollama] = FailingModel
    assert (
        client.post(
            url + "/messages", headers=headers, json={"content": "Следующий вопрос"}
        ).status_code
        == 503
    )
    assert len(client.get(url, headers=headers).json()["messages"]) == 2
    assert session.get(Chat, chat_id).generation_id is None
    chat = session.get(Chat, chat_id)
    chat.generation_id = "other-request"
    chat.generation_started_at = datetime.now(UTC)
    session.commit()
    assert (
        client.post(
            url + "/messages", headers=headers, json={"content": "Ещё вопрос"}
        ).status_code
        == 409
    )


class FakeGitHub:
    calls = 0

    def start(self, workflow_file, branch, request_id):
        self.request_id = request_id
        self.calls += 1
        return {"id": 601, "name": "Aurora #601"}

    def build(self, run_id):
        return {
            "id": 601,
            "path": ".github/workflows/portal.yml",
            "head_branch": "main",
            "display_title": f"NIRS {self.request_id}",
            "status": "completed",
            "conclusion": "failure",
            "head_sha": "abc123",
            "run_started_at": "2026-11-13T10:00:00Z",
            "updated_at": "2026-11-13T10:10:00Z",
        }

    def jobs(self, run_id):
        return [
            {
                "id": 5,
                "name": "Compile",
                "started_at": "2026-11-13T10:00:00Z",
                "completed_at": "2026-11-13T10:01:00Z",
                "status": "completed",
                "conclusion": "failure",
            }
        ]

    def artifacts(self, run_id):
        return [{"id": 9, "name": "test-report", "expired": False}]

    def log(self, run_id, log_id):
        return "compiler error: missing Qt header\npassword=hidden"

    def download(self, run_id, name):
        yield b"PK-test-archive"


def test_build_lifecycle_ownership_logs_artifact_and_analysis(
    client, session, monkeypatch
):
    headers = account(client)
    other = account(client, "other@example.com")
    pipeline = Pipeline(name="Aurora", workflow_file="portal.yml")
    session.add(pipeline)
    session.commit()
    fake = FakeGitHub()
    for module in (
        "routers.pipelines",
        "routers.runs",
        "routers.jobs",
        "services.chats",
    ):
        monkeypatch.setattr(module + ".get_github", lambda: fake)
    url = f"/pipelines/{pipeline.id}/start"
    request_headers = dict(headers, **{"Idempotency-Key": "request-unique-123"})
    run_id = client.post(url, headers=request_headers, json={}).json()["id"]
    assert client.post(url, headers=request_headers, json={}).json()["id"] == run_id
    assert fake.calls == 1
    assert (
        client.post(
            url, headers=request_headers, json={"branch": "different"}
        ).status_code
        == 409
    )
    assert client.get(f"/api/runs/{run_id}", headers=other).status_code == 404
    assert client.get("/api/runs", headers=other).json() == []
    data = client.get(f"/api/runs/{run_id}", headers=headers).json()
    assert data["status"] == "completed" and data["result"] == "failed"
    assert data["commit_sha"] == "abc123"
    assert data["finished_at"] == "2026-11-13T10:01:00Z"
    job_id = data["jobs"][0]["id"]
    artifact_id = data["artifacts"][0]["id"]
    # Repeated polling updates records rather than inserting duplicate jobs/artifacts.
    assert client.get(f"/api/runs/{run_id}/status", headers=headers).status_code == 200
    from services.runs import sync_run

    sync_run(session, session.get(Run, run_id), fake)
    assert len(list(session.scalars(select(Job)))) == 1
    assert len(list(session.scalars(select(Artifact)))) == 1
    assert client.get(f"/api/jobs/{job_id}", headers=other).status_code == 404
    assert client.get(f"/jobs/{job_id}/log", headers=other).status_code == 404
    log = client.get(f"/jobs/{job_id}/log", headers=headers).text
    assert "hidden" not in log and "[REDACTED]" in log
    download = f"/api/artifacts/{artifact_id}/download"
    assert client.get(download, headers=other).status_code == 404
    assert client.get(download, headers=headers).content == b"PK-test-archive"
    analysis = client.post(f"/api/runs/{run_id}/analysis", headers=headers)
    assert analysis.status_code == 201
    chat_id = analysis.json()["id"]
    assert (
        client.get(f"/api/chats/{chat_id}", headers=headers).json()["run_id"] == run_id
    )
    assert len(list(session.scalars(select(Message)))) == 2


def test_ambiguous_submission_never_retries(client, session, monkeypatch):
    headers = account(client)
    pipeline = Pipeline(name="Aurora", workflow_file="portal.yml")
    session.add(pipeline)
    session.commit()

    class UncertainGitHub(FakeGitHub):
        def start(self, workflow_file, branch, request_id):
            self.request_id = request_id
            self.calls += 1
            raise SubmissionUnknown()

    fake = UncertainGitHub()
    monkeypatch.setattr("routers.pipelines.get_github", lambda: fake)
    headers["Idempotency-Key"] = "uncertain-request"
    url = f"/pipelines/{pipeline.id}/start"
    run_id = client.post(url, json={}, headers=headers).json()["id"]
    assert session.get(Run, run_id).status == "submission_unknown"
    assert client.post(url, json={}, headers=headers).json()["id"] == run_id
    assert fake.calls == 1


def test_unconfigured_github_creates_no_fake_run(client, session, monkeypatch):
    from config import get_settings

    headers = account(client)
    settings = get_settings().model_copy(update={"github_owner": ""})
    monkeypatch.setattr("services.github.get_settings", lambda: settings)
    pipeline = Pipeline(name="Aurora", workflow_file="portal.yml")
    session.add(pipeline)
    session.commit()
    response = client.post(f"/pipelines/{pipeline.id}/start", headers=headers, json={})
    assert response.status_code == 503
    assert list(session.scalars(select(Run))) == []
