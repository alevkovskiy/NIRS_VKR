import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from config import BASE_DIR, get_settings
from models import User
from models.entities import AccessSession
from schemas.auth import Credentials
from schemas.responses import TokenRead, UserRead
from security import CurrentUser, Db, hash_password, token_digest, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])
_attempts = defaultdict(deque)
_attempts_lock = Lock()
# Avoid revealing whether an email exists through a cheap missing-user path.
_DUMMY_HASH = hash_password("not-a-real-user-password")


def throttle(request: Request):
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _attempts_lock:
        for key in list(_attempts):
            if not _attempts[key] or _attempts[key][-1] < now - 60:
                del _attempts[key]
        attempts = _attempts[address]
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 15:
            raise HTTPException(429, "Слишком много попыток. Подождите минуту.")
        attempts.append(now)


@router.get("")
@router.get("/")
def auth_page():
    return FileResponse(BASE_DIR / "templates/login.html")


@router.get("/register")
def register_page():
    return FileResponse(BASE_DIR / "templates/register.html")


@router.post("/register/send", status_code=201, response_model=UserRead)
def register(data: Credentials, request: Request, db: Db):
    throttle(request)
    user = User(
        email=str(data.email).lower(), password_hash=hash_password(data.password)
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Аккаунт с этой почтой уже существует.") from exc
    return {"id": user.id, "email": user.email}


@router.post("/send", response_model=TokenRead)
def login(data: Credentials, request: Request, db: Db, response: Response):
    throttle(request)
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    valid = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if not valid or user is None:
        raise HTTPException(401, "Неверная почта или пароль")
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.execute(delete(AccessSession).where(AccessSession.expires_at < now))
    db.add(
        AccessSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=now + timedelta(hours=get_settings().session_hours),
        )
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=204)
def logout(request: Request, db: Db, user: CurrentUser):
    token = request.headers.get("authorization", "").split(" ", 1)[-1]
    db.execute(
        delete(AccessSession).where(
            AccessSession.user_id == user.id,
            AccessSession.token_hash == token_digest(token),
        )
    )
    db.commit()
    return Response(status_code=204)
