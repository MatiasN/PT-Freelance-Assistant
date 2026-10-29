from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})
    return _engine


# Columns added after the first release. `create_all` only creates missing tables, so an
# existing SQLite file gets them here (SQLite supports ADD COLUMN; NOT NULL is backfilled).
SCHEMA_UPGRADES: list[tuple[str, str, str, str | None]] = [
    # (table, column, ADD COLUMN definition, backfill statement)
    ("payout", "rate_date", "rate_date DATE", None),
    (
        "payout",
        "irs_currency_per_eur",
        "irs_currency_per_eur NUMERIC(12, 6)",
        "UPDATE payout SET irs_currency_per_eur = currency_per_eur",
    ),
    ("payout", "irs_rate_date", "irs_rate_date DATE", None),
    (
        "payout",
        "irs_eur_amount",
        "irs_eur_amount NUMERIC(12, 2)",
        "UPDATE payout SET irs_eur_amount = eur_amount",
    ),
]


def upgrade_schema(engine: Engine) -> list[str]:
    """Add columns missing from tables created by an older version. Returns what was added."""
    inspector = inspect(engine)
    added: list[str] = []
    with engine.begin() as connection:
        for table, column, definition, backfill in SCHEMA_UPGRADES:
            if not inspector.has_table(table):
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            if column in existing:
                continue
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))
            if backfill:
                connection.execute(text(backfill))
            added.append(f"{table}.{column}")
    return added


def init_db(engine: Engine | None = None) -> None:
    """Start-up schema step: add columns missing from old tables, then create missing tables
    (`create_all` never alters existing tables)."""
    engine = engine or get_engine()
    upgrade_schema(engine)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
