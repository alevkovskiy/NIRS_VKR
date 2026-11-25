import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from config import get_settings
from models import Chat, DiagnosticCheck, Pipeline, Run, User
from routers import diagnostics, pipelines
from tests.test_api import TestModel, account

pytest_plugins = ("tests.test_api",)


def test_diagnostics_from_registration_to_report(
    client, session, monkeypatch, tmp_path
):
    headers = account(client)
    outsider = account(client, "other@example.com")
    owner_id = session.scalar(select(User.id).where(User.email == "owner@example.com"))
    pipeline = Pipeline(name="Тесты", workflow_file="portal.yml")
    session.add(pipeline)
    session.flush()
    run = Run(
        user_id=owner_id,
        pipeline_id=pipeline.id,
        name="Повторный прогон",
        status="completed",
        result="succeeded",
        branch="main",
    )
    session.add(run)
    session.commit()
    run_id = run.id
    snapshot = tmp_path / "latest.json"
    settings = get_settings().model_copy(update={"testops_stand_report": snapshot})
    monkeypatch.setattr(diagnostics, "get_settings", lambda: settings)
    generated = []

    def generate(_self, messages):
        if not generated:
            generated.append(None)
            raise HTTPException(503, "Модель недоступна.")
        generated.append(messages)
        return "Черновик: исходящий вызов завершился тайм-аутом."

    monkeypatch.setattr(TestModel, "generate", generate)
    body = {
        "request_id": str(uuid4()),
        "title": "Тайм-аут исходящего вызова",
        "diagnosis": {"bench": "CALL-01", "observed": "Тайм-аут"},
        "attachment": {"name": "stand.log", "text": "ERROR timeout\npassword=demo"},
        "run_id": run_id,
    }
    created = client.post("/api/diagnostics", headers=headers, json=body)
    assert created.status_code == 201
    diagnostic_id = created.json()["id"]
    replay = client.post("/api/diagnostics", headers=headers, json=body)
    assert replay.status_code == 200 and replay.json()["id"] == diagnostic_id
    assert session.scalar(select(func.count(Chat.id))) == 1
    assert client.get("/api/diagnostics", headers=outsider).json() == []
    path = f"/api/diagnostics/{diagnostic_id}"
    assert client.get(path, headers=outsider).status_code == 404
    assert client.post(f"{path}/report", headers=outsider).status_code == 404
    assert client.post(f"{path}/stand", headers=headers).status_code == 503
    evidence = {
        "check_id": str(uuid4()),
        "bench": "CALL-02",
        "name": "Звонок",
        "outcome": "failed",
        "note": "Превышено время ожидания.",
        "measured_at": datetime.now(UTC).isoformat(),
    }
    snapshot.write_text(json.dumps(evidence))
    assert client.post(f"{path}/stand", headers=headers).status_code == 409
    evidence["bench"] = "CALL-01"
    snapshot.write_text(json.dumps(evidence))
    stand = client.post(f"{path}/stand", headers=headers)
    assert stand.status_code == 200
    assert stand.json()["source"] == "stand"
    assert (
        client.post(f"{path}/stand", headers=headers).json()["id"] == stand.json()["id"]
    )
    manual = {
        "request_id": str(uuid4()),
        "name": "Уровень сигнала",
        "outcome": "passed",
        "note": "Проверка вручную",
    }
    assert (
        client.post(f"{path}/checks", headers=headers, json=manual).status_code == 200
    )
    assert (
        client.post(f"{path}/checks", headers=headers, json=manual).status_code == 200
    )
    ci = client.post(f"{path}/ci/{run_id}", headers=headers)
    assert ci.status_code == 200 and ci.json()["outcome"] == "passed"
    dispatched = []

    class GitHub:
        def start(self, workflow, branch, request_id):
            dispatched.append((workflow, branch, request_id))
            return {"id": 1234}

    monkeypatch.setattr(pipelines, "get_github", GitHub)
    repeat_body = {"request_id": str(uuid4())}
    assert (
        client.post(f"{path}/repeat", headers=outsider, json=repeat_body).status_code
        == 404
    )
    repeat = client.post(f"{path}/repeat", headers=headers, json=repeat_body)
    assert repeat.status_code == 201
    assert repeat.json()["id"] != run_id
    replayed = client.post(f"{path}/repeat", headers=headers, json=repeat_body)
    assert replayed.json() == repeat.json()
    assert len(dispatched) == 1
    assert dispatched[0][:2] == ("portal.yml", "main")
    assert session.scalar(select(func.count(DiagnosticCheck.id))) == 3
    saved = client.get(path, headers=headers).json()
    assert saved["run_id"] == run_id
    assert set(check["source"] for check in saved["checks"]) == {
        "manual",
        "stand",
        "ci",
    }
    assert "password=[REDACTED]" in saved["log_excerpt"]
    assert client.post(f"{path}/report", headers=headers).status_code == 503
    chat_path = f"/api/chats/{saved['chat_id']}"
    assert client.get(chat_path, headers=headers).json()["messages"] == []
    report = client.post(f"{path}/report", headers=headers)
    assert report.status_code == 200
    assert "Уровень сигнала" in generated[-1][-1]["content"]
    assert "ERROR timeout" in generated[-1][-1]["content"]
    assert "Контекст прогона" in generated[-1][0]["content"]
    history = client.get(chat_path, headers=headers).json()["messages"]
    assert history[1]["content"] == report.json()["assistant_message"]["content"]
    for status in ("resolved", "open"):
        updated = client.post(
            f"{path}/status", headers=headers, json={"status": status}
        )
        assert updated.status_code == 200 and updated.json()["status"] == status


def test_stand_source_defaults_to_disabled(client, session, monkeypatch):
    headers = account(client)
    settings = get_settings().model_copy(update={"testops_stand_report": None})
    monkeypatch.setattr(diagnostics, "get_settings", lambda: settings)
    body = {
        "request_id": str(uuid4()),
        "title": "Тайм-аут",
        "diagnosis": {"bench": "CALL-01", "observed": "Сбой"},
    }
    item = client.post("/api/diagnostics", headers=headers, json=body).json()
    path = f"/api/diagnostics/{item['id']}"
    assert not client.get(path, headers=headers).json()["stand_available"]
    assert client.post(f"{path}/stand", headers=headers).status_code == 409
