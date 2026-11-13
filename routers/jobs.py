from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import select

from config import BASE_DIR
from crud.access import owned_job, owned_run
from models import Artifact
from schemas.responses import JobRead
from security import CurrentUser, Db
from services.github import get_github
from services.runs import scrub_log

router = APIRouter(tags=["Jobs and artifacts"])


@router.get("/jobs/{job_id}")
def job_page(job_id: str):
    return FileResponse(BASE_DIR / "templates/job.html")


@router.get("/api/jobs/{job_id}", response_model=JobRead)
def job(job_id: int, db: Db, user: CurrentUser):
    return owned_job(db, job_id, user.id)


@router.get("/jobs/{job_id}/log", response_class=PlainTextResponse)
def log(job_id: int, db: Db, user: CurrentUser):
    job = owned_job(db, job_id, user.id)
    run = owned_run(db, job.run_id, user.id)
    external_id, log_id = run.external_run_id, job.external_log_id
    db.commit()
    if external_id is None or log_id is None:
        return "Журнал этой задачи пока недоступен."
    return scrub_log(get_github().log(external_id, log_id))


@router.get("/api/artifacts/{artifact_id}/download")
def download(artifact_id: int, db: Db, user: CurrentUser):
    artifact = db.scalar(select(Artifact).where(Artifact.id == artifact_id))
    if artifact is None:
        raise HTTPException(404, "Артефакт не найден")
    run = owned_run(db, artifact.run_id, user.id)
    external_id, name = run.external_run_id, artifact.external_artifact_id
    if external_id is None:
        raise HTTPException(409, "Запуск не связан с GitHub")
    github = get_github()
    iterator = github.download(external_id, name)
    # Open the upstream response before starting a 200 response to the browser.
    try:
        first = next(iterator)
    except StopIteration:
        first = b""
    except HTTPException:
        iterator.close()
        raise
    except Exception as exc:
        iterator.close()
        raise HTTPException(502, "Не удалось скачать артефакт GitHub.") from exc

    def chunks():
        try:
            yield first
            yield from iterator
        finally:
            iterator.close()

    db.commit()
    return StreamingResponse(
        chunks(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="artifact-{artifact_id}.zip"',
            "Cache-Control": "no-store",
        },
    )
