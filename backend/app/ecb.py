"""HTTP client for the ECB Data Portal (euro foreign exchange reference rates).

ECB Data Portal REST API (SDMX 2.1 web service), documented at
https://data.ecb.europa.eu/help/api/overview and https://data.ecb.europa.eu/help/api/data:

* entry point ``https://data-api.ecb.europa.eu/service``
* data query ``GET /data/{flowRef}/{key}`` with ``startPeriod``/``endPeriod`` (ISO dates for
  daily series), ``detail=dataonly`` (observations without attributes) and ``format=csvdata``
* the reference-rate dataflow is ``EXR``; its key is
  ``FREQ.CURRENCY.CURRENCY_DENOM.EXR_TYPE.EXR_SUFFIX`` — ``D.USD.EUR.SP00.A`` is the daily
  USD/EUR spot reference rate (average), expressed as units of currency per 1 EUR
* status codes: 200 data, 404 "No results found" (query matched nothing), 400 syntax error,
  500/503 server error or service unavailable

Reference rates are published once a day around 16:00 CET on TARGET business days only
(https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/).
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import httpx2 as httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://data-api.ecb.europa.eu/service"
DATAFLOW = "EXR"
USER_AGENT = "pt-tax-assistant/0.1 (self-hosted ledger; ECB reference-rate lookup)"

# HTTP 404 "No results found" is the documented answer to a query that matches no
# observations (e.g. a date range covering only non-publication days).
NO_RESULTS_STATUS = 404


class EcbUnavailable(RuntimeError):
    """The ECB Data Portal could not be reached or returned something we cannot use."""


@dataclass(frozen=True)
class EcbObservation:
    rate_date: date
    currency_per_eur: Decimal


def series_key(currency: str) -> str:
    return f"D.{currency.upper()}.EUR.SP00.A"


def series_page_url(currency: str) -> str:
    """Human-readable ECB Data Portal page for the series (shown to the user as the source)."""
    return f"https://data.ecb.europa.eu/data/datasets/{DATAFLOW}/{DATAFLOW}.{series_key(currency)}"


def parse_csv_observations(body: str) -> list[EcbObservation]:
    """Parse ``format=csvdata`` output: one row per observation with TIME_PERIOD and OBS_VALUE."""
    if not body.strip():
        return []
    reader = csv.DictReader(io.StringIO(body))
    if reader.fieldnames is None or not {"TIME_PERIOD", "OBS_VALUE"} <= set(reader.fieldnames):
        raise EcbUnavailable("ECB response is not the expected CSV (TIME_PERIOD/OBS_VALUE)")

    observations: list[EcbObservation] = []
    for row in reader:
        raw_value = (row.get("OBS_VALUE") or "").strip()
        raw_period = (row.get("TIME_PERIOD") or "").strip()
        if not raw_value:
            continue  # missing observation (e.g. OBS_STATUS "-")
        try:
            observations.append(EcbObservation(date.fromisoformat(raw_period), Decimal(raw_value)))
        except (ValueError, InvalidOperation) as error:
            raise EcbUnavailable(f"ECB response has an unreadable observation: {row}") from error
    observations.sort(key=lambda observation: observation.rate_date)
    return observations


class EcbClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"User-Agent": USER_AGENT, "Accept": "text/csv"},
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def fetch_daily_rates(self, currency: str, start: date, end: date) -> list[EcbObservation]:
        """Daily reference rates for ``currency`` against EUR between ``start`` and ``end``.

        Returns an empty list when the ECB has no observation in the range. Raises
        :class:`EcbUnavailable` for network errors, timeouts, server errors and bodies we
        cannot parse, so the caller can map them to HTTP 502.
        """
        path = f"/data/{DATAFLOW}/{series_key(currency)}"
        params = {
            "startPeriod": start.isoformat(),
            "endPeriod": end.isoformat(),
            "detail": "dataonly",
            "format": "csvdata",
        }
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as error:
            logger.warning("ECB Data Portal request failed: %s", error)
            raise EcbUnavailable(f"ECB Data Portal request failed: {error}") from error

        if response.status_code == NO_RESULTS_STATUS:
            return []
        if response.status_code != 200:
            logger.warning("ECB Data Portal answered HTTP %s", response.status_code)
            raise EcbUnavailable(f"ECB Data Portal answered HTTP {response.status_code}")
        return parse_csv_observations(response.text)


# --- TARGET calendar -------------------------------------------------------------------------
# The ECB publishes reference rates only on TARGET business days. TARGET closing days, besides
# weekends: New Year's Day, Good Friday, Easter Monday, 1 May, Christmas Day and 26 December.
# https://www.ecb.europa.eu/paym/target/target2/profuse/calendar/html/index.en.html


def easter_sunday(year: int) -> date:
    """Gregorian Easter (Meeus/Jones/Butcher algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def target_closing_reason(day: date) -> str | None:
    """Why the ECB does not publish a reference rate on ``day``, or None on a business day."""
    if day.weekday() == 5:
        return "Saturday"
    if day.weekday() == 6:
        return "Sunday"
    easter = easter_sunday(day.year)
    holidays: dict[date, str] = {
        date(day.year, 1, 1): "New Year's Day",
        easter - timedelta(days=2): "Good Friday",
        easter + timedelta(days=1): "Easter Monday",
        date(day.year, 5, 1): "Labour Day",
        date(day.year, 12, 25): "Christmas Day",
        date(day.year, 12, 26): "26 December",
    }
    return holidays.get(day)


def previous_target_business_day(day: date) -> date:
    """Latest TARGET business day strictly before ``day``."""
    candidate = day - timedelta(days=1)
    while target_closing_reason(candidate) is not None:
        candidate -= timedelta(days=1)
    return candidate
