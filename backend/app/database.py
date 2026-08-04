"""Engine and session for the Supabase Session Pooler (see PRD section 13)."""

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
_pool_kwargs = (
    {}
    if settings.database_url.startswith("sqlite")
    else dict(pool_size=5, max_overflow=5, pool_timeout=30, pool_pre_ping=True)
)

engine = create_engine(settings.database_url, connect_args=_connect_args, **_pool_kwargs)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
