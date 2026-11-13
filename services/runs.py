import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from config import get_settings
from crud.access import get_pipeline
from models import Artifact, Job, Run
from services.github import GitHubClient

STATUS = {
    "queued": "queued",
    "requested": "queued",
    "waiting": "queued",
    "pending": "queued",
    "in_progress": "in_progress",
    "completed": "completed",
}
RESULT = {
    "success": "succeeded",
    "failure": "failed",
    "cancelled": "canceled",
    "timed_out": "failed",
    "action_required": "failed",
    "startup_failure": "failed",
    "stale": "failed",
    "neutral": "partially_succeeded",
    "skipped": "skipped",
}


def parsed_date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def scrub_log(value: str) -> str:
    pat = get_settings().github_token.get_secret_value()
    if pat:
        value = value.replace(pat, "[REDACTED]")
    value = re.sub(
        r"(?i)(authorization[:=]\s*(?:bearer|basic)\s+)\S+", r"\1[REDACTED]", value
    )
    value = re.sub(
        r"(?i)((?:password|access_token|api_key|secret)\s*[:=]\s*)\S+",
        r"\1[REDACTED]",
        value,
    )
    return value


def sync_run(db: Session, run: Run, github: GitHubClient) -> Run:
    local_id, external_id = run.id, run.external_run_id
    workflow_file = get_pipeline(db, run.pipeline_id).workflow_file
    branch, request_id = run.branch, run.request_id
    db.commit()
    if external_id is None:
        if not request_id or run.status == "submission_failed":
            return run
        db.commit()
        external_id = github.find_run(workflow_file, branch, request_id)
        if external_id is None:
            return run
    build = github.build(external_id)
    expected_path = f".github/workflows/{workflow_file}"
    if build.get("path", "").split("@", 1)[0] != expected_path:
        raise HTTPException(502, "GitHub вернул запуск другого процесса сборки.")
    if build.get("head_branch") != branch.removeprefix("refs/heads/"):
        raise HTTPException(502, "GitHub вернул запуск другой ветки.")
    if request_id and build.get("display_title") != f"NIRS {request_id}":
        raise HTTPException(502, "GitHub вернул запуск с другим ключом запроса.")
    records = github.jobs(external_id)
    artifacts = (
        github.artifacts(external_id) if build.get("status") == "completed" else []
    )
    run = db.scalar(
        select(Run)
        .where(Run.id == local_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    run.external_run_id = external_id
    run.submission_error = None
    if run.status != "completed":
        status = STATUS.get(build.get("status"))
        if status is None:
            raise HTTPException(502, "GitHub вернул неизвестный статус запуска.")
        run.status = status
        conclusion = build.get("conclusion")
        mapped = RESULT.get(conclusion)
        run.result = (
            ("partially_succeeded" if mapped == "skipped" else mapped)
            if status == "completed"
            else None
        )
        run.commit_sha = build.get("head_sha")
        run.started_at = parsed_date(build.get("run_started_at"))
        # updated_at also changes after completion, so it is not a finish time.
        completions = [
            parsed_date(job.get("completed_at"))
            for job in records
            if job.get("completed_at")
        ]
        run.finished_at = (
            max(completions) if status == "completed" and completions else None
        )
    for record in records:
        job_id = record.get("id")
        if not job_id:
            continue
        values = dict(
            run_id=local_id,
            external_job_id=str(job_id),
            attempt=record.get("run_attempt") or build.get("run_attempt") or 1,
            name=record.get("name") or "Задача",
            status=STATUS.get(record.get("status"), "pending"),
            result=RESULT.get(record.get("conclusion")),
            external_log_id=job_id if record.get("status") == "completed" else None,
            started_at=parsed_date(record.get("started_at")),
            finished_at=parsed_date(record.get("completed_at")),
        )
        db.execute(
            insert(Job)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[Job.run_id, Job.external_job_id, Job.attempt],
                set_=values,
            )
        )
    for artifact in artifacts:
        if artifact.get("expired") or not artifact.get("id"):
            continue
        db.execute(
            insert(Artifact)
            .values(
                run_id=local_id,
                name=artifact["name"],
                external_artifact_id=str(artifact["id"]),
            )
            .on_conflict_do_nothing(
                index_elements=[Artifact.run_id, Artifact.external_artifact_id]
            )
        )
    db.commit()
    return run


def serialize_run(db: Session, run: Run, full: bool = True) -> dict:
    pipeline = get_pipeline(db, run.pipeline_id)
    fields = (
        "id",
        "name",
        "pipeline_id",
        "status",
        "result",
        "created_at",
        "started_at",
        "finished_at",
        "branch",
        "commit_sha",
        "submission_error",
    )
    result = {field: getattr(run, field) for field in fields}
    result["pipeline_name"] = pipeline.name
    if full:
        result["jobs"] = list(
            db.scalars(select(Job).where(Job.run_id == run.id).order_by(Job.id))
        )
        result["artifacts"] = [
            {"id": a.id, "name": a.name}
            for a in db.scalars(
                select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.id)
            )
        ]
    return result
