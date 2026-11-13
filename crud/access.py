from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Chat, Job, Pipeline, Run


def owned_run(db: Session, run_id: int, user_id: int) -> Run:
    run = db.scalar(select(Run).where(Run.id == run_id, Run.user_id == user_id))
    if run is None:
        raise HTTPException(404, "Прогон не найден")
    return run


def owned_chat(db: Session, chat_id: int, user_id: int) -> Chat:
    chat = db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
    if chat is None:
        raise HTTPException(404, "Чат не найден")
    return chat


def owned_job(db: Session, job_id: int, user_id: int) -> Job:
    job = db.scalar(
        select(Job).join(Run).where(Job.id == job_id, Run.user_id == user_id)
    )
    if job is None:
        raise HTTPException(404, "Задача не найдена")
    return job


def get_pipeline(db: Session, pipeline_id: int) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(404, "Пайплайн не найден")
    return pipeline
