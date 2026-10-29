from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, SQLModel, select

import app.db as db_module
from app.config import Settings, get_settings
from app.db import get_engine, get_session, init_db, upgrade_schema
from app.main import app
from app.models import Payout

OLD_PAYOUT_TABLE = """
CREATE TABLE payout (
    payout_date DATE NOT NULL,
    currency VARCHAR(3) NOT NULL,
    original_amount NUMERIC(12, 2) NOT NULL,
    currency_per_eur NUMERIC(12, 6) NOT NULL,
    client_name VARCHAR(200),
    notes VARCHAR(2000),
    invoice_number VARCHAR(50),
    invoice_issued_on DATE,
    id INTEGER NOT NULL PRIMARY KEY,
    eur_amount NUMERIC(12, 2) NOT NULL,
    created_at DATETIME NOT NULL
)
"""


def _old_database(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text(OLD_PAYOUT_TABLE))
        connection.execute(
            text(
                "INSERT INTO payout (payout_date, currency, original_amount, currency_per_eur, "
                "id, eur_amount, created_at) VALUES ('2026-03-06', 'USD', 1085.00, 1.085, 1, "
                "1000.00, '2026-03-06 17:00:00')"
            )
        )
    return engine


def test_upgrade_adds_the_rate_columns_and_backfills_existing_rows(tmp_path):
    engine = _old_database(tmp_path)

    added = upgrade_schema(engine)
    SQLModel.metadata.create_all(engine)

    assert added == [
        "payout.rate_date",
        "payout.irs_currency_per_eur",
        "payout.irs_rate_date",
        "payout.irs_eur_amount",
    ]
    with Session(engine) as session:
        payout = session.exec(select(Payout)).one()
        assert payout.irs_currency_per_eur == Decimal("1.085")
        assert payout.irs_eur_amount == Decimal("1000.00")
        assert payout.rate_date is None and payout.irs_rate_date is None


def test_upgrade_is_idempotent_and_skips_fresh_databases(tmp_path):
    old = _old_database(tmp_path)
    upgrade_schema(old)
    assert upgrade_schema(old) == []

    fresh = create_engine("sqlite://")
    assert upgrade_schema(fresh) == []  # no tables yet: nothing to do
    SQLModel.metadata.create_all(fresh)
    assert upgrade_schema(fresh) == []
    columns = {col["name"] for col in inspect(fresh).get_columns("payout")}
    assert {"rate_date", "irs_currency_per_eur", "irs_rate_date", "irs_eur_amount"} <= columns


def _columns(engine, table: str) -> set[str]:
    return {col["name"] for col in inspect(engine).get_columns(table)}


def test_provenance_lives_in_a_new_table_and_never_alters_the_payout_table(tmp_path):
    """A database created by the previous version: `payout` already has the IRS columns but
    there is no provenance table yet, and one payout was recorded without provenance."""
    engine = _old_database(tmp_path)
    upgrade_schema(engine)  # the previous version's start-up (adds the IRS columns)
    payout_columns_before = _columns(engine, "payout")
    tables_before = set(inspect(engine).get_table_names())
    assert "payout_rate_provenance" not in tables_before

    init_db(engine)  # this version's start-up

    assert _columns(engine, "payout") == payout_columns_before  # no new columns, ever
    assert set(inspect(engine).get_table_names()) == tables_before | {
        "payout_rate_provenance",
        "exchange_rate",
    }

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        client = TestClient(app)
        (old,) = client.get("/api/payouts", params={"year": 2026}).json()
        assert old["id"] == 1
        assert old["rate_provenance"] is None and old["irs_rate_provenance"] is None

        provenance = {
            "source": "ecb",
            "requested_date": "2026-03-09",
            "ecb_rate_date": "2026-03-09",
            "ecb_currency_per_eur": "1.0820",
            "is_fallback": False,
            "fallback_reason": None,
            "fetched_at": "2026-03-09T16:05:00Z",
        }
        new = client.post(
            "/api/payouts",
            json={
                "payout_date": "2026-03-09",
                "currency": "USD",
                "original_amount": "1082.00",
                "currency_per_eur": "1.0820",
                "rate_provenance": provenance,
                "irs_rate_provenance": provenance,
            },
        ).json()
        assert new["rate_provenance"]["source"] == "ecb"
        assert new["irs_rate_provenance"]["ecb_rate_date"] == "2026-03-09"

        (old_again,) = [p for p in client.get("/api/payouts").json() if p["id"] == 1]
        assert old_again["rate_provenance"] is None
    finally:
        app.dependency_overrides.clear()
    assert _columns(engine, "payout") == payout_columns_before


@pytest.fixture
def configured_engine(tmp_path, monkeypatch):
    """Point the real settings at a fresh SQLite file and reset the process-wide engine."""
    db_file = tmp_path / "nested" / "dir" / "pt-tax.db"
    monkeypatch.setenv("PTTAX_DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()
    monkeypatch.setattr(db_module, "_engine", None)
    yield db_file
    get_settings.cache_clear()


def test_get_engine_creates_the_sqlite_directory_and_is_a_singleton(configured_engine):
    engine = get_engine()

    assert configured_engine.parent.is_dir()  # created so SQLite can open the file
    assert get_engine() is engine
    assert str(engine.url).endswith("pt-tax.db")


def test_init_db_without_an_engine_uses_the_configured_one(configured_engine):
    init_db()

    assert configured_engine.is_file()
    assert {"payout", "exchange_rate", "payout_rate_provenance"} <= set(
        inspect(get_engine()).get_table_names()
    )


def test_get_session_yields_a_session_on_the_configured_engine(configured_engine):
    init_db()
    sessions = list(get_session())

    assert len(sessions) == 1
    assert sessions[0].get_bind() is get_engine()
