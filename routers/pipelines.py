from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import BASE_DIR
from crud.access import get_pipeline
from models import Pipeline, Run
from schemas.responses import IdRead, PipelineRead
from schemas.runs import RunCreate
from security import CurrentUser, Db
from services.github import SubmissionUnknown, get_github

router = APIRouter(tags=["Pipelines"])


@router.get("/pipelines")
@router.get("/pipelines/")
def pipelines_page():
    return FileResponse(BASE_DIR / "templates/pipelines.html")


@router.get("/pipelines/{pipeline_id}")
def pipeline_page(pipeline_id: str):
    return FileResponse(BASE_DIR / "templates/pipeline.html")


def summary(pipeline):
    return {
        key: getattr(pipeline, key)
        for key in ("id", "name", "description", "default_branch")
    }


@router.get("/api/pipelines", response_model=list[PipelineRead])
def pipelines(db: Db, user: CurrentUser):
    return [summary(p) for p in db.scalars(select(Pipeline).order_by(Pipeline.id))]


@router.get("/api/pipelines/{pipeline_id}", response_model=PipelineRead)
def pipeline(pipeline_id: int, db: Db, user: CurrentUser):
    return summary(get_pipeline(db, pipeline_id))


@router.post("/pipelines/{pipeline_id}/start", status_code=201, response_model=IdRead)
def start(
    pipeline_id: int,
    data: RunCreate,
    db: Db,
    user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(max_length=64, min_length=8)] = None,
):
    pipeline = get_pipeline(db, pipeline_id)
    owner_id = user.id
    branch = data.branch or pipeline.default_branch
    if idempotency_key:
        existing = db.scalar(
            select(Run).where(
                Run.user_id == owner_id, Run.idempotency_key == idempotency_key
            )
        )
        if existing:
            if existing.pipeline_id != pipeline_id or existing.branch != branch:
                raise HTTPException(
                    409, "Ключ запроса уже использован с другими параметрами."
                )
            return {"id": existing.id}
    github = (
        get_github()
    )  # fail before inserting if no credentials have been configured
    workflow_file = pipeline.workflow_file
    run = Run(
        pipeline_id=pipeline_id,
        user_id=owner_id,
        branch=branch,
        name=f"{pipeline.name} — {branch}",
        idempotency_key=idempotency_key,
        request_id=str(uuid4()),
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not idempotency_key:
            raise HTTPException(409, "Конфликт создания запуска") from None
        existing = db.scalar(
            select(Run).where(
                Run.user_id == owner_id, Run.idempotency_key == idempotency_key
            )
        )
        if (
            existing
            and existing.pipeline_id == pipeline_id
            and existing.branch == branch
        ):
            return {"id": existing.id}
        raise HTTPException(409, "Конфликт создания запуска") from None
    local_id, request_id = run.id, run.request_id
    db.commit()
    try:
        result = github.start(workflow_file, branch, request_id)
    except SubmissionUnknown:
        run.status = "submission_unknown"
        run.submission_error = (
            "Ответ GitHub потерян. Запуск мог быть создан. "
            "Проверьте GitHub перед новой попыткой."
        )
    except HTTPException:
        run.status = "submission_failed"
        run.submission_error = (
            "GitHub отклонил запуск. Проверьте настройки и права доступа."
        )
    else:
        run.external_run_id = result["id"]
        run.status = "queued"
        run.name = result.get("name") or run.name
    db.commit()
    return {"id": local_id}
