from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url.get_secret_value(), pool_pre_ping=True
    )


def get_db() -> Generator[Session]:
    # CRUD calls flush(); the service commits the complete transaction explicitly.
    with Session(get_engine()) as session:
        yield session
