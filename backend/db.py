from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import JSON, ForeignKey, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class SearchTask(Base):
    __tablename__ = 'search_tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    query: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default='queued', index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    started_at: Mapped[str | None]
    ended_at: Mapped[str | None]
    error: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON)


class TaskEvent(Base):
    __tablename__ = 'task_events'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('search_tasks.id', ondelete='CASCADE'), index=True)
    type: Mapped[str]
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)


class Competition(Base):
    __tablename__ = 'competitions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    data: Mapped[dict] = mapped_column(JSON)


class CompetitionSource(Base):
    __tablename__ = 'competition_sources'
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[str] = mapped_column(ForeignKey('competitions.id', ondelete='CASCADE'), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str]
    source_type: Mapped[str]
    captured_at: Mapped[str]
    verification_status: Mapped[str]
    excerpt: Mapped[str] = mapped_column(Text)


class TaskCompetition(Base):
    __tablename__ = 'task_competitions'
    task_id: Mapped[str] = mapped_column(ForeignKey('search_tasks.id', ondelete='CASCADE'), primary_key=True)
    competition_id: Mapped[str] = mapped_column(ForeignKey('competitions.id', ondelete='CASCADE'), primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON)


engine = create_engine(f'sqlite:///{settings.data_dir / "saitan.db"}', connect_args={'check_same_thread': False})


@event.listens_for(engine, 'connect')
def configure_sqlite(connection, _):
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('PRAGMA busy_timeout=5000')


Session = sessionmaker(engine, expire_on_commit=False)


def event_dict(e):
    return {k: getattr(e, k) for k in ('id', 'task_id', 'type', 'message', 'payload', 'created_at')}
