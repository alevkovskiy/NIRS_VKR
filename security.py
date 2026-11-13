import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User
from models.entities import AccessSession

Db = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except ValueError, TypeError:
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        401, "Войдите в аккаунт", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None or len(credentials.credentials) > 256:
        raise unauthorized
    user = db.scalar(
        select(User)
        .join(AccessSession, AccessSession.user_id == User.id)
        .where(
            AccessSession.token_hash == token_digest(credentials.credentials),
            AccessSession.expires_at > datetime.now(UTC),
        )
    )
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(current_user)]
