from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from config import BASE_DIR
from crud.access import owned_run
from models import Chat, Run
from models.enums import RunResult
from schemas.responses import IdRead, RunRead, RunSummary
from security import CurrentUser, Db
from services.chats import send_message
from services.github import get_github
from services.ollama import OllamaClient, get_ollama
from services.runs import serialize_run, sync_run

router = APIRouter(tags=["Runs"])


@router.get("/runs")
@router.get("/runs/")
def runs_page():
    return FileResponse(BASE_DIR / "templates/runs.html")


@router.get("/runs/{run_id}")
def run_page(run_id: str):
    return FileResponse(BASE_DIR / "templates/run.html")


@router.get("/api/runs", response_model=list[RunSummary])
def runs(
    db: Db,
    user: CurrentUser,
    pipeline_id: Annotated[int | None, Query(gt=0)] = None,
    result: RunResult | None = None,
):
    statement = select(Run).where(Run.user_id == user.id)
    if pipeline_id is not None:
        statement = statement.where(Run.pipeline_id == pipeline_id)
    if result is not None:
        statement = statement.where(Run.result == result.value)
    return [
        serialize_run(db, r, full=False)
        for r in db.scalars(
            statement.order_by(Run.created_at.desc(), Run.id.desc()).limit(200)
        )
    ]


@router.get("/api/runs/{run_id}", response_model=RunRead)
@router.get("/api/runs/{run_id}/status", response_model=RunRead)
def run_detail(run_id: int, db: Db, user: CurrentUser):
    run = owned_run(db, run_id, user.id)
    if run.status not in ("completed", "submission_failed"):
        run = sync_run(db, run, get_github())
    return serialize_run(db, run)


@router.post("/api/runs/{run_id}/analysis", status_code=201, response_model=IdRead)
def analyze(
    run_id: int,
    db: Db,
    user: CurrentUser,
    ollama: Annotated[OllamaClient, Depends(get_ollama)],
):
    owner_id = user.id
    run = owned_run(db, run_id, owner_id)
    if run.status not in ("completed", "submission_failed"):
        run = sync_run(db, run, get_github())
    if run.status in ("pending", "queued", "in_progress"):
        raise HTTPException(
            409, "Дождитесь завершения прогона для анализа результатов."
        )
    chat = Chat(user_id=owner_id, run_id=run_id, title=f"Разбор прогона #{run_id}")
    db.add(chat)
    db.commit()
    chat_id = chat.id
    send_message(
        db,
        chat_id,
        owner_id,
        "Разбери результат этого прогона. Укажи факты, возможную причину "
        "ошибки и следующие проверки. Если журналов нет, сообщи об этом.",
        ollama,
    )
    return {"id": chat_id}
