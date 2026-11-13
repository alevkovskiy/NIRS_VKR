from alembic import context
from sqlalchemy import create_engine, pool

import models  # noqa: F401 -- register all tables for autogenerate
from config import get_settings
from database import Base


def run_migrations_offline():
    context.configure(
        url=get_settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(
        get_settings().database_url.get_secret_value(), poolclass=pool.NullPool
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
