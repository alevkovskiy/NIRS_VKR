import re
from collections.abc import Iterator
from urllib.parse import quote, urlparse

import httpx
from fastapi import HTTPException

from config import get_settings

MAX_LOG_BYTES = 2 * 1024 * 1024


class SubmissionUnknown(Exception):
    """The dispatch may have succeeded. Do not repeat it automatically."""


class GitHubClient:
    def __init__(self):
        settings = get_settings()
        if not settings.github_configured:
            raise HTTPException(503, "GitHub Actions ещё не подключён на сервере.")
        if not all(
            re.fullmatch(r"[A-Za-z0-9_.-]+", part)
            for part in [settings.github_owner, settings.github_repo]
        ):
            raise HTTPException(503, "Проверьте имя владельца и репозитория GitHub.")
        self.base = (
            f"https://api.github.com/repos/{settings.github_owner}/"
            f"{settings.github_repo}/"
        )
        self.headers = {
            "Authorization": f"Bearer {settings.github_token.get_secret_value()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }

    def request(self, method: str, path: str, **kwargs) -> dict:
        try:
            with httpx.Client(timeout=15, trust_env=False) as client:
                response = client.request(
                    method, self.base + path, headers=self.headers, **kwargs
                )
                if response.status_code >= 500 and method == "POST":
                    raise SubmissionUnknown()
                if response.status_code in (401, 403):
                    raise HTTPException(
                        502, "GitHub отклонил доступ. Проверьте токен и права Actions."
                    )
                if response.status_code == 404:
                    raise HTTPException(
                        502,
                        "Репозиторий, процесс сборки или запуск не найден в GitHub.",
                    )
                if response.status_code == 410:
                    raise HTTPException(
                        410, "Срок хранения артефакта или журнала истёк."
                    )
                if response.is_error:
                    raise HTTPException(
                        502,
                        "GitHub отклонил запрос. Проверьте ветку и настройки Actions.",
                    )
                if response.status_code == 204:
                    return {}
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected object")
                return data
        except (httpx.TransportError, ValueError) as exc:
            if method == "POST":
                raise SubmissionUnknown() from exc
            raise HTTPException(
                502, "Не удалось получить данные GitHub Actions."
            ) from exc

    def workflow(self, workflow_file: str) -> dict:
        return self.request("GET", f"actions/workflows/{quote(workflow_file, safe='')}")

    def start(self, workflow_file: str, branch: str, request_id: str) -> dict:
        data = self.request(
            "POST",
            f"actions/workflows/{quote(workflow_file, safe='')}/dispatches",
            json={
                "ref": branch.removeprefix("refs/heads/"),
                "inputs": {"portal_request_id": request_id},
            },
        )
        # Current API returns the run ID. Older GitHub versions return 204;
        # that case is resolved by the unique request ID in run-name.
        if not data:
            return {"id": None}
        run_id = data.get("workflow_run_id")
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
            raise SubmissionUnknown()
        return {"id": run_id}

    def find_run(self, workflow_file: str, branch: str, request_id: str) -> int | None:
        for page in range(1, 6):
            data = self.request(
                "GET",
                f"actions/workflows/{quote(workflow_file, safe='')}/runs",
                params={
                    "event": "workflow_dispatch",
                    "branch": branch.removeprefix("refs/heads/"),
                    "per_page": 100,
                    "page": page,
                },
            )
            runs = data.get("workflow_runs", [])
            matches = [
                run["id"]
                for run in runs
                if run.get("display_title") == f"NIRS {request_id}"
            ]
            if len(matches) > 1:
                raise HTTPException(409, "Найдены дубли запроса. Проверьте GitHub.")
            if matches:
                return matches[0]
            if len(runs) < 100:
                return None
        return None

    def build(self, run_id: int) -> dict:
        return self.request("GET", f"actions/runs/{run_id}")

    def _collection(self, path: str, key: str, **params) -> list[dict]:
        items = []
        for page in range(1, 21):
            data = self.request(
                "GET", path, params={**params, "per_page": 100, "page": page}
            )
            batch = data.get(key, [])
            items.extend(batch)
            if len(batch) < 100:
                return items
        raise HTTPException(502, "Слишком много задач или артефактов в запуске.")

    def jobs(self, run_id: int) -> list[dict]:
        return self._collection(f"actions/runs/{run_id}/jobs", "jobs", filter="latest")

    def artifacts(self, run_id: int) -> list[dict]:
        return self._collection(f"actions/runs/{run_id}/artifacts", "artifacts")

    def _stream(
        self, path: str, limit: int, *, truncate: bool = False
    ) -> Iterator[bytes]:
        url = self.base + path
        with httpx.Client(timeout=15, trust_env=False) as client:
            for _ in range(6):
                parsed = urlparse(url)
                host = parsed.hostname or ""
                trusted = (
                    host == "api.github.com"
                    or host.endswith(".actions.githubusercontent.com")
                    or host.endswith(".blob.core.windows.net")
                )
                if (
                    parsed.scheme != "https"
                    or not trusted
                    or parsed.username
                    or parsed.port not in (None, 443)
                ):
                    raise HTTPException(
                        502, "GitHub вернул недопустимый адрес скачивания."
                    )
                headers = self.headers if url.startswith(self.base) else {}
                with client.stream("GET", url, headers=headers) as response:
                    if response.is_redirect:
                        url = str(response.url.join(response.headers["location"]))
                        continue
                    if response.status_code in (404, 410):
                        raise HTTPException(
                            410, "Журнал или артефакт больше недоступен в GitHub."
                        )
                    response.raise_for_status()
                    total = 0
                    for chunk in response.iter_bytes():
                        if total + len(chunk) > limit:
                            if not truncate:
                                raise HTTPException(
                                    413, "Скачиваемый файл превышает лимит."
                                )
                            yield chunk[: limit - total]
                            return
                        total += len(chunk)
                        yield chunk
                    return
            raise HTTPException(502, "Слишком много перенаправлений GitHub.")

    def log(self, run_id: int, log_id: int) -> str:
        job = self.request("GET", f"actions/jobs/{log_id}")
        if job.get("run_id") != run_id:
            raise HTTPException(502, "Журнал относится к другому запуску.")
        try:
            data = b"".join(
                self._stream(
                    f"actions/jobs/{log_id}/logs", MAX_LOG_BYTES, truncate=True
                )
            )
            suffix = "\n[Журнал обрезан до 2 МБ]" if len(data) >= MAX_LOG_BYTES else ""
            return data.decode("utf-8", errors="replace") + suffix
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Не удалось скачать журнал GitHub.") from exc

    def download(self, run_id: int, artifact_id: str) -> Iterator[bytes]:
        if not artifact_id.isdecimal():
            raise HTTPException(502, "Некорректный ID артефакта.")
        metadata = self.request("GET", f"actions/artifacts/{artifact_id}")
        if metadata.get("workflow_run", {}).get("id") != run_id:
            raise HTTPException(502, "Артефакт относится к другому запуску.")
        if metadata.get("expired"):
            raise HTTPException(410, "Срок хранения артефакта истёк.")
        if metadata.get("size_in_bytes", 0) > 256 * 1024 * 1024:
            raise HTTPException(413, "Артефакт превышает лимит 256 МБ.")
        try:
            yield from self._stream(
                f"actions/artifacts/{artifact_id}/zip", 256 * 1024 * 1024
            )
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Не удалось скачать артефакт GitHub.") from exc


def get_github() -> GitHubClient:
    return GitHubClient()
