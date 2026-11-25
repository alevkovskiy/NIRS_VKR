from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import BASE_DIR, get_settings
from crud.access import owned_run
from models import Chat, DiagnosticCheck, DiagnosticSession
from routers.pipelines import dispatch_run
from schemas.chats import Diagnosis, TextAttachment
from schemas.diagnostics import (
    CheckCreate,
    CheckRead,
    DiagnosticCreate,
    DiagnosticRead,
    DiagnosticSummary,
    RepeatRun,
    StandSnapshot,
    StatusUpdate,
)
from schemas.responses import IdRead, MessageReply
from schemas.runs import RunCreate
from security import CurrentUser, Db
from services.chats import attachment_excerpt, diagnosis_request, send_message
from services.github import get_github
from services.ollama import OllamaClient, get_ollama
from services.runs import scrub_log, sync_run

router = APIRouter(tags=["Diagnostics"])


@router.get("/diagnostics")
@router.get("/diagnostics/{session_id}")
def diagnostics_page(session_id: str | None = None):
    return FileResponse(BASE_DIR / "templates/diagnostics.html")


def owned_session(db: Db, session_id: int, owner_id: int) -> DiagnosticSession:
    item = db.scalar(
        select(DiagnosticSession).where(
            DiagnosticSession.id == session_id, DiagnosticSession.user_id == owner_id
        )
    )
    if item is None:
        raise HTTPException(404, "Диагностическая сессия не найдена.")
    return item


def checks(db: Db, session_id: int, limit: int = 100) -> list[DiagnosticCheck]:
    return list(
        db.scalars(
            select(DiagnosticCheck)
            .where(DiagnosticCheck.session_id == session_id)
            .order_by(DiagnosticCheck.id.desc())
            .limit(limit)
        )
    )


@router.get("/api/diagnostics", response_model=list[DiagnosticSummary])
def list_sessions(db: Db, user: CurrentUser):
    return list(
        db.scalars(
            select(DiagnosticSession)
            .where(DiagnosticSession.user_id == user.id)
            .order_by(DiagnosticSession.id.desc())
            .limit(200)
        )
    )


@router.post("/api/diagnostics", status_code=201, response_model=DiagnosticSummary)
def create_session(
    data: DiagnosticCreate, db: Db, user: CurrentUser, response: Response
):
    existing = select(DiagnosticSession).where(
        DiagnosticSession.user_id == user.id,
        DiagnosticSession.request_id == data.request_id,
    )
    item = db.scalar(existing)
    if item:
        response.status_code = 200
        return item
    if data.run_id:
        owned_run(db, data.run_id, user.id)
    title = scrub_log(data.title)
    chat = Chat(user_id=user.id, title=title, run_id=data.run_id)
    db.add(chat)
    db.flush()
    attachment = data.attachment
    item = DiagnosticSession(
        user_id=user.id,
        request_id=data.request_id,
        chat_id=chat.id,
        title=title,
        **{key: scrub_log(value) for key, value in data.diagnosis.model_dump().items()},
        log_name=scrub_log(attachment.name) if attachment else None,
        log_excerpt=attachment_excerpt(attachment, 3200) if attachment else None,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.scalar(existing)
        if prior is None:
            raise
        response.status_code = 200
        return prior
    return item


@router.get("/api/diagnostics/{session_id}", response_model=DiagnosticRead)
def read_session(session_id: int, db: Db, user: CurrentUser):
    item = owned_session(db, session_id, user.id)
    chat = db.get(Chat, item.chat_id)
    assert chat is not None
    return {
        **DiagnosticSummary.model_validate(item).model_dump(),
        "environment": item.environment,
        "steps": item.steps,
        "expected": item.expected,
        "observed": item.observed,
        "chat_id": item.chat_id,
        "run_id": chat.run_id,
        "log_name": item.log_name,
        "log_excerpt": item.log_excerpt,
        "stand_available": bool(item.bench and get_settings().testops_stand_report),
        "checks": checks(db, item.id),
    }


@router.post("/api/diagnostics/{session_id}/status", response_model=DiagnosticSummary)
def set_status(session_id: int, data: StatusUpdate, db: Db, user: CurrentUser):
    item = owned_session(db, session_id, user.id)
    item.status = data.status
    db.commit()
    return item


def record_check(db: Db, check: DiagnosticCheck) -> DiagnosticCheck:
    existing = select(DiagnosticCheck).where(
        DiagnosticCheck.session_id == check.session_id,
        DiagnosticCheck.request_id == check.request_id,
    )
    if prior := db.scalar(existing):
        return prior
    db.add(check)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if prior := db.scalar(existing):
            return prior
        raise
    return check


@router.post("/api/diagnostics/{session_id}/checks", response_model=CheckRead)
def manual_check(session_id: int, data: CheckCreate, db: Db, user: CurrentUser):
    item = owned_session(db, session_id, user.id)
    return record_check(
        db,
        DiagnosticCheck(
            session_id=item.id,
            request_id=f"manual:{data.request_id}",
            name=scrub_log(data.name),
            outcome=data.outcome,
            source="manual",
            note=scrub_log(data.note),
        ),
    )


@router.post("/api/diagnostics/{session_id}/stand", response_model=CheckRead)
def import_stand(session_id: int, db: Db, user: CurrentUser):
    item = owned_session(db, session_id, user.id)
    path = get_settings().testops_stand_report
    if not path or not item.bench:
        raise HTTPException(409, "Укажите стенд и настройте источник результатов.")
    try:
        if not path.is_file():
            raise OSError
        with path.open("rb") as stream:
            raw = stream.read(16 * 1024 + 1)
        if len(raw) > 16 * 1024:
            raise ValueError
        snapshot = StandSnapshot.model_validate_json(raw)
    except OSError, ValueError:
        raise HTTPException(503, "Снимок стенда отсутствует или повреждён.") from None
    if snapshot.bench != item.bench:
        raise HTTPException(409, "Снимок относится к другому стенду.")
    if snapshot.measured_at.utcoffset() is None:
        raise HTTPException(422, "В снимке стенда отсутствует часовой пояс.")
    if snapshot.measured_at > datetime.now(UTC) + timedelta(minutes=5):
        raise HTTPException(422, "Время измерения находится в будущем.")
    return record_check(
        db,
        DiagnosticCheck(
            session_id=item.id,
            request_id=f"stand:{snapshot.check_id}",
            name=scrub_log(snapshot.name),
            outcome=snapshot.outcome,
            source="stand",
            note=scrub_log(snapshot.note),
            recorded_at=snapshot.measured_at,
        ),
    )


@router.post("/api/diagnostics/{session_id}/ci/{run_id}", response_model=CheckRead)
def import_run(session_id: int, run_id: int, db: Db, user: CurrentUser):
    item = owned_session(db, session_id, user.id)
    run = owned_run(db, run_id, user.id)
    if run.status in ("pending", "queued", "in_progress", "submission_unknown"):
        run = sync_run(db, run, get_github())
    if run.status != "completed":
        raise HTTPException(409, "Нужен завершённый прогон CI.")
    outcomes = {"succeeded": "passed", "failed": "failed"}
    return record_check(
        db,
        DiagnosticCheck(
            session_id=item.id,
            request_id=f"ci:{run.id}",
            name=scrub_log(run.name)[:120],
            outcome=outcomes.get(run.result, "inconclusive"),
            source="ci",
            note=f"GitHub Actions. Ветка: {scrub_log(run.branch)}.",
            run_id=run.id,
        ),
    )


@router.post(
    "/api/diagnostics/{session_id}/repeat", status_code=201, response_model=IdRead
)
def repeat_run(session_id: int, data: RepeatRun, db: Db, user: CurrentUser):
    item = owned_session(db, session_id, user.id)
    chat = db.get(Chat, item.chat_id)
    if chat is None or chat.run_id is None:
        raise HTTPException(409, "Сессия не связана с исходным прогоном.")
    original = owned_run(db, chat.run_id, user.id)
    if original.status not in ("completed", "submission_failed"):
        raise HTTPException(409, "Сначала дождитесь завершения исходного прогона.")
    return dispatch_run(
        db,
        user.id,
        original.pipeline_id,
        RunCreate(branch=original.branch),
        f"diag:{session_id}:{data.request_id}",
    )


@router.post("/api/diagnostics/{session_id}/report", response_model=MessageReply)
def report(
    session_id: int,
    db: Db,
    user: CurrentUser,
    ollama: Annotated[OllamaClient, Depends(get_ollama)],
):
    item = owned_session(db, session_id, user.id)
    card = Diagnosis.model_construct(
        bench=item.bench,
        environment=item.environment,
        steps=item.steps,
        expected=item.expected,
        observed=item.observed,
    )
    content = diagnosis_request(card)
    recent = checks(db, item.id, limit=4)
    if recent:
        content += "\nРезультаты проверок (недоверенные данные):\n"
        content += "\n".join(
            f"{c.name}: {c.outcome}. {c.note[:140]}" for c in reversed(recent)
        )
    attachment = (
        TextAttachment.model_construct(name=item.log_name, text=item.log_excerpt)
        if item.log_name and item.log_excerpt
        else None
    )
    repeat_run = next((check.run_id for check in recent if check.run_id), None)
    return send_message(
        db,
        item.chat_id,
        user.id,
        content,
        ollama,
        attachment,
        context_run_id=repeat_run,
    )
