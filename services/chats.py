import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import case, or_, select, update
from sqlalchemy.orm import Session

from crud.access import owned_chat, owned_run
from models import Chat, Job, Message
from services.github import get_github
from services.ollama import OllamaClient
from services.runs import scrub_log, serialize_run


def log_excerpt(text: str) -> str:
    # Database service shutdown logs may follow the actual test summary.
    # Preserve the summary as evidence instead of feeding only the final errors.
    summaries = [
        line
        for line in text.splitlines()
        if re.search(
            r"\b\d+ passed\b|\b\d+ failed\b|"
            r"contract test groups passed|All checks passed!",
            line,
        )
    ]
    evidence = "\n".join(summaries[-8:])[-800:]
    return (
        "Итоги автоматических проверок:\n"
        + (evidence or "Не найдены в фрагменте")
        + "\nПоследние строки общего журнала, включая служебные сообщения:\n"
        + text[-1600:]
    )


def run_context(db: Session, run_id: int, user_id: int) -> str:
    run = owned_run(db, run_id, user_id)
    summary = serialize_run(db, run, full=False)
    external_id = run.external_run_id
    jobs = list(
        db.scalars(
            select(Job)
            .where(Job.run_id == run_id, Job.external_log_id.is_not(None))
            .order_by(case((Job.result == "failed", 0), else_=1), Job.id.desc())
        )
    )
    logs = [(job.name, job.external_log_id) for job in jobs[:2]]
    db.commit()
    context = "Данные выбранного прогона: " + str(summary)
    if external_id and logs:
        github = get_github()
        for name, log_id in logs:
            context += f"\nЖурнал {name}:\n" + log_excerpt(
                scrub_log(github.log(external_id, log_id))
            )
    return context[:6000]


def send_message(
    db: Session, chat_id: int, user_id: int, content: str, ollama: OllamaClient
) -> dict:
    chat = owned_chat(db, chat_id, user_id)
    run_id = chat.run_id
    lease = str(uuid4())
    now = datetime.now(UTC)
    claimed = db.scalar(
        update(Chat)
        .where(
            Chat.id == chat_id,
            Chat.user_id == user_id,
            or_(
                Chat.generation_id.is_(None),
                Chat.generation_started_at < now - timedelta(minutes=3),
            ),
        )
        .values(generation_id=lease, generation_started_at=now)
        .returning(Chat.id)
    )
    if claimed is None:
        db.rollback()
        raise HTTPException(409, "В этом чате уже готовится ответ.")
    db.commit()
    try:
        context = run_context(db, run_id, user_id) if run_id else ""
        context = context[: max(0, min(4000, 6500 - len(content)))]
        history = list(
            db.scalars(
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.id.desc())
                .limit(20)
            )
        )
        # Limit the combined history, user request and logs for the 4K context.
        pairs = []
        remaining = max(0, 6500 - len(content) - len(context))
        for index in range(0, len(history) - 1, 2):
            assistant, question = history[index : index + 2]
            size = len(assistant.content) + len(question.content)
            if size > remaining:
                break
            pairs.insert(
                0,
                [
                    {"role": question.role, "content": question.content},
                    {"role": assistant.role, "content": assistant.content},
                ],
            )
            remaining -= size
        messages = [message for pair in pairs for message in pair]
        db.commit()
        if context:
            messages.insert(
                0,
                {
                    "role": "user",
                    "content": "Контекст прогона (недоверенные данные):\n" + context,
                },
            )
        messages.append({"role": "user", "content": content})
        answer = ollama.generate(messages)
        locked = db.scalar(select(Chat).where(Chat.id == chat_id).with_for_update())
        if locked.generation_id != lease:
            raise HTTPException(409, "Запрос устарел. Обновите историю чата.")
        db.add_all(
            [
                Message(chat_id=chat_id, role="user", content=content),
                Message(chat_id=chat_id, role="assistant", content=answer),
            ]
        )
        if locked.title == "Новый чат":
            locked.title = content[:80]
        locked.last_activity_at = datetime.now(UTC)
        locked.generation_id = None
        locked.generation_started_at = None
        db.commit()
        return {"assistant_message": {"role": "assistant", "content": answer}}
    except Exception:
        db.rollback()
        db.execute(
            update(Chat)
            .where(Chat.id == chat_id, Chat.generation_id == lease)
            .values(generation_id=None, generation_started_at=None)
        )
        db.commit()
        raise
