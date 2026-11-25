"""Run an isolated TestOps web demo with synthetic CI and model responses."""

import argparse
import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from unittest.mock import patch

import uvicorn
from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session

import main
from config import get_settings
from database import Base, get_engine
from models import Pipeline, User
from routers import diagnostics, jobs, pipelines, runs
from security import hash_password
from services import chats
from services.ollama import get_ollama

EMAIL = "demo@example.com"
PASSWORD = "testops-demo-2026"
PIPELINE = "Тесты веб-клиента (демо)"
LOGS = {
    False: (
        "INFO build=web-client assets=ok\n"
        "ERROR test=save_diagnostic expected=201 actual=504\n"
        "1 failed, 4 passed\n"
    ),
    True: "INFO build=web-client assets=ok\n5 passed\n",
}


class DemoModel:
    def available(self):
        return True

    def generate(self, messages):
        evidence = "\n".join(message["content"] for message in messages)
        repeat = (
            "Повторный прогон: 5 тестов прошли."
            if "5 passed" in evidence
            else "Запишите результат повторного прогона."
        )
        failure = (
            "Исходный журнал: test=save_diagnostic, ожидался HTTP 201, получен 504."
            if "save_diagnostic" in evidence
            else "Сверьте фактический результат с журналом исходного прогона."
        )
        return (
            "Демонстрационный черновик баг-репорта\n\n"
            f"{failure}\n{repeat}\n"
            "Причина тайм-аута по этим данным не установлена.\n"
            "Следующая проверка: сверить время запроса с журналом приложения."
        )


class DemoGitHub:
    def __init__(self):
        self._lock = Lock()
        self._builds = {}

    def start(self, workflow, branch, request_id):
        with self._lock:
            run_id = len(self._builds) + 1
            self._builds[run_id] = (workflow, branch, request_id)
        return {"id": run_id, "name": f"{PIPELINE} #{run_id}"}

    def build(self, run_id):
        try:
            workflow, branch, request_id = self._builds[run_id]
        except KeyError:
            raise HTTPException(404, "Демонстрационный прогон не найден.") from None
        return {
            "path": f".github/workflows/{workflow}",
            "head_branch": branch.removeprefix("refs/heads/"),
            "display_title": f"NIRS {request_id}",
            "status": "completed",
            "conclusion": "success" if run_id > 1 else "failure",
            "head_sha": f"{run_id:040x}",
        }

    def jobs(self, run_id):
        now = datetime.now(UTC).isoformat()
        return [
            {
                "id": run_id,
                "name": "Сборка и тесты веб-клиента (демо)",
                "status": "completed",
                "conclusion": self.build(run_id)["conclusion"],
                "started_at": now,
                "completed_at": now,
            }
        ]

    def artifacts(self, run_id):
        return []

    def log(self, run_id, log_id):
        self.build(run_id)
        if log_id != run_id:
            raise HTTPException(404, "Демонстрационный журнал не найден.")
        return LOGS[run_id > 1]


@contextmanager
def demo_app(data_dir: Path) -> Iterator[FastAPI]:
    database = data_dir / "testops.sqlite3"
    flags = {
        "DATABASE_URL": f"sqlite:///{database}",
        "GH_ACTIONS_TOKEN": "",
        "OLLAMA_MODEL": "Демонстрационные ответы",
        "TESTOPS_STAND_REPORT": "",
    }
    github = DemoGitHub()
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, flags))
        get_settings.cache_clear()
        get_engine.cache_clear()
        engine = get_engine()
        stack.callback(get_settings.cache_clear)
        stack.callback(get_engine.cache_clear)
        stack.callback(engine.dispose)
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all(
                [
                    User(email=EMAIL, password_hash=hash_password(PASSWORD)),
                    Pipeline(
                        name=PIPELINE,
                        description="Синтетический сценарий: сбой и успешный повтор.",
                        workflow_file="portal.yml",
                    ),
                ]
            )
            db.commit()
        for module in (chats, diagnostics, jobs, pipelines, runs):
            stack.enter_context(patch.object(module, "get_github", lambda: github))
        stack.enter_context(
            patch.dict(main.app.dependency_overrides, {get_ollama: DemoModel})
        )
        stack.enter_context(
            patch.object(main.app.state, "demo_mode", True, create=True)
        )
        yield main.app


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="testops-web-demo-") as directory:
        with demo_app(Path(directory)) as app:
            print(f"http://127.0.0.1:{args.port} — {EMAIL} / {PASSWORD}", flush=True)
            uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    cli()
