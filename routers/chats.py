from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from config import BASE_DIR
from crud.access import owned_chat, owned_run
from models import Chat, Message
from schemas.chats import ChatCreate, MessageCreate
from schemas.responses import ChatRead, ChatSummary, MessageReply
from security import CurrentUser, Db
from services.chats import send_message
from services.ollama import OllamaClient, get_ollama

router = APIRouter(tags=["Chats"])


@router.get("/chats")
@router.get("/chats/")
def chats_page():
    return FileResponse(BASE_DIR / "templates/chats.html")


@router.get("/chats/{chat_id}")
def chat_page(chat_id: str):
    return FileResponse(BASE_DIR / "templates/chat.html")


def summary(chat):
    return {
        key: getattr(chat, key)
        for key in ("id", "title", "run_id", "created_at", "last_activity_at")
    }


@router.get("/api/chats", response_model=list[ChatSummary])
def chats(db: Db, user: CurrentUser, q: Annotated[str, Query(max_length=200)] = ""):
    statement = select(Chat).where(Chat.user_id == user.id)
    if q:
        statement = statement.where(Chat.title.contains(q, autoescape=True))
    return [
        summary(chat)
        for chat in db.scalars(
            statement.order_by(Chat.last_activity_at.desc(), Chat.id.desc()).limit(200)
        )
    ]


@router.post("/chats/new", status_code=201, response_model=ChatSummary)
def create_chat(data: ChatCreate, db: Db, user: CurrentUser):
    if data.run_id:
        owned_run(db, data.run_id, user.id)
    chat = Chat(user_id=user.id, title=data.title, run_id=data.run_id)
    db.add(chat)
    db.commit()
    return summary(chat)


@router.get("/api/chats/{chat_id}", response_model=ChatRead)
def read_chat(chat_id: int, db: Db, user: CurrentUser):
    chat = owned_chat(db, chat_id, user.id)
    result = summary(chat)
    result["messages"] = [
        {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in db.scalars(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.id)
        )
    ]
    return result


@router.post("/api/chats/{chat_id}/messages", response_model=MessageReply)
def message(
    chat_id: int,
    data: MessageCreate,
    db: Db,
    user: CurrentUser,
    ollama: Annotated[OllamaClient, Depends(get_ollama)],
):
    return send_message(db, chat_id, user.id, data.content, ollama)
