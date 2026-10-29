import csv
import io
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import Settings, get_settings
from app.db import get_session
from app.ecb import EcbClient
from app.exchange_rates import get_ecb_client
from app.fiscal.parameters import FiscalParameters, get_fiscal_parameters
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parameters_2026() -> FiscalParameters:
    return get_fiscal_parameters(2026)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def ecb_usd_csv() -> str:
    """Synthetic `format=csvdata` payload for EXR/D.USD.EUR.SP00.A: Feb–Apr 2026 and
    Dec 2026–Dec 2027 (see generate_ecb_fixture.py)."""
    first = (FIXTURES / "ecb_exr_usd_2026.csv").read_text()
    header, _, rest = (FIXTURES / "ecb_exr_usd_2026-12_2027.csv").read_text().partition("\n")
    assert first.startswith(header)
    return first + rest


@pytest.fixture
def ecb_live_csv() -> bytes:
    """Byte-exact excerpt of a real `detail=dataonly&format=csvdata` answer (8 columns, CRLF).

    Captured on 2026-03 from
    https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2026-03-02&endPeriod=2026-03-06&detail=dataonly&format=csvdata
    """
    return (FIXTURES / "ecb_exr_usd_dataonly_live.csv").read_bytes()


class FakeEcb:
    """Stand-in for the ECB Data Portal behind an httpx MockTransport (no sockets involved).

    By default it behaves like the real service: it returns the fixture rows whose
    TIME_PERIOD falls inside startPeriod..endPeriod, or HTTP 404 "No results found" when
    nothing matches. Tests can swap in any other behaviour with :meth:`respond_with`.
    """

    def __init__(self, csv_body: str) -> None:
        self.csv_body = csv_body
        self.requests: list[httpx.Request] = []
        self._responder: Callable[[httpx.Request], httpx.Response] = self._filtered_fixture

    def respond_with(
        self,
        response: httpx.Response | Exception | Callable[[httpx.Request], httpx.Response],
    ) -> None:
        if callable(response):
            self._responder = response
            return

        def responder(_: httpx.Request) -> httpx.Response:
            if isinstance(response, Exception):
                raise response
            return response

        self._responder = responder

    def fixture_response(self, request: httpx.Request) -> httpx.Response:
        """The default behaviour, for custom responders that want to wrap it."""
        return self._filtered_fixture(request)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responder(request)

    def _filtered_fixture(self, request: httpx.Request) -> httpx.Response:
        start = request.url.params.get("startPeriod", "0000-00-00")
        end = request.url.params.get("endPeriod", "9999-99-99")
        reader = csv.DictReader(io.StringIO(self.csv_body))
        assert reader.fieldnames is not None
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
        writer.writeheader()
        matched = 0
        for row in reader:
            if start <= row["TIME_PERIOD"] <= end:
                writer.writerow(row)
                matched += 1
        if matched == 0:
            return httpx.Response(404, text="No results found.")
        return httpx.Response(200, text=out.getvalue(), headers={"content-type": "text/csv"})

    def client(self) -> EcbClient:
        return EcbClient("https://ecb.test/service", transport=httpx.MockTransport(self.handle))


@pytest.fixture
def fake_ecb(ecb_usd_csv: str) -> FakeEcb:
    return FakeEcb(ecb_usd_csv)


@pytest.fixture
def engine() -> Engine:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def file_engine(tmp_path: Path) -> Engine:
    """SQLite on disk: every session gets its own connection, so real concurrency is possible
    (the in-memory `engine` shares one connection through StaticPool)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _make_client(settings: Settings, engine: Engine, fake_ecb: FakeEcb) -> Iterator[TestClient]:
    def session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_ecb_client] = fake_ecb.client
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client(settings: Settings, engine: Engine, fake_ecb: FakeEcb) -> Iterator[TestClient]:
    yield from _make_client(settings, engine, fake_ecb)


@pytest.fixture
def file_client(settings: Settings, file_engine: Engine, fake_ecb: FakeEcb) -> Iterator[TestClient]:
    yield from _make_client(settings, file_engine, fake_ecb)
