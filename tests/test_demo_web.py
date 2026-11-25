from uuid import uuid4

from fastapi.testclient import TestClient

from demo_web import EMAIL, LOGS, PASSWORD, demo_app


def test_demo_web_acceptance(tmp_path):
    with demo_app(tmp_path) as app, TestClient(app) as client:
        for path, marker in {
            "/": "TestOps Assistant",
            "/auth/": "auth-form",
            "/diagnostics": "diagnostic-form",
            "/static/js/app.js": "async function diagnostics",
            "/static/css/style.css": ".diagnostic-form",
        }.items():
            response = client.get(path)
            assert response.status_code == 200 and marker in response.text
        assert client.get("/health/ready").json() == {"status": "ok"}
        login = client.post("/auth/send", json={"email": EMAIL, "password": PASSWORD})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        system = client.get("/api/system/status", headers=headers).json()
        assert system["demo"] and not system["github"]["configured"]
        pipeline = client.get("/api/pipelines", headers=headers).json()[0]["id"]
        started = client.post(f"/pipelines/{pipeline}/start", headers=headers, json={})
        original = started.json()["id"]
        failed = client.get(f"/api/runs/{original}", headers=headers).json()
        assert failed["result"] == "failed"
        job = failed["jobs"][0]["id"]
        assert client.get(f"/jobs/{job}/log", headers=headers).text == LOGS[False]
        created = client.post(
            "/api/diagnostics",
            json={
                "request_id": str(uuid4()),
                "title": "Сохранение карточки вернуло 504",
                "diagnosis": {"observed": "HTTP 504"},
                "attachment": {"name": "web-ci.log", "text": LOGS[False]},
                "run_id": original,
            },
            headers=headers,
        )
        assert created.status_code == 201
        page = f"/diagnostics/{created.json()['id']}"
        assert "diagnostic-detail" in client.get(page).text
        path = f"/api{page}"
        repeat = client.post(
            f"{path}/repeat", json={"request_id": str(uuid4())}, headers=headers
        )
        repeated = repeat.json()["id"]
        assert repeated != original
        assert client.get(f"/api/runs/{repeated}", headers=headers).json()[
            "result"
        ] == ("succeeded")
        for run, outcome in ((original, "failed"), (repeated, "passed")):
            check = client.post(f"{path}/ci/{run}", headers=headers)
            assert check.status_code == 200 and check.json()["outcome"] == outcome
        report = client.post(f"{path}/report", headers=headers)
        assert report.status_code == 200
        answer = report.json()["assistant_message"]["content"]
        assert "получен 504" in answer and "5 тестов прошли" in answer
        finished = client.post(
            f"{path}/status", json={"status": "resolved"}, headers=headers
        )
        assert finished.json()["status"] == "resolved"
        saved = client.get(path, headers=headers).json()
        assert len(saved["checks"]) == 2
        chat = client.get(f"/api/chats/{saved['chat_id']}", headers=headers).json()
        assert chat["messages"][-1]["content"] == answer
        from_run = client.post(
            "/api/diagnostics",
            json={
                "request_id": str(uuid4()),
                "title": "Сбой из прогона без отдельного вложения",
                "diagnosis": {},
                "run_id": original,
            },
            headers=headers,
        )
        from_run_path = f"/api/diagnostics/{from_run.json()['id']}"
        assert (
            client.post(f"{from_run_path}/ci/{repeated}", headers=headers).status_code
            == 200
        )
        from_runs = client.post(f"{from_run_path}/report", headers=headers)
        text = from_runs.json()["assistant_message"]["content"]
        assert "получен 504" in text and "5 тестов прошли" in text
