"""ECB reference-rate lookup with a local cache and business-day fallback.

The day whose rate applies is decided by :mod:`app.fiscal.currency_conversion` (CIVA art. 49.º
with art. 8.º n.º 1; CIRS art. 23.º). This module only fetches and caches the ECB rate for that
day, falling back to the last previous business day when the ECB published nothing
(CIRS art. 23.º n.º 3: "aplica-se o da última cotação anterior").

Banco de Portugal no longer quotes its own buy/sell rates; it publishes the ECB euro reference
rates, which is why the ECB Data Portal is used as the official source.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.config import Settings, get_settings
from app.ecb import (
    EcbClient,
    EcbObservation,
    previous_target_business_day,
    series_page_url,
    target_closing_reason,
)
from app.fiscal.currency_conversion import LEGAL_BASIS, conversion_date
from app.models import Currency, ExchangeRate, ExchangeRateRead, FallbackReason, RateLookup

# Longest run of TARGET closing days is 4 (e.g. Good Friday to Easter Monday, or Christmas
# Day + 26 December + weekend); a two-week window leaves room for unexpected closures.
LOOKBACK_DAYS = 14

logger = logging.getLogger(__name__)

SOURCE = "European Central Bank — euro foreign exchange reference rates (ECB Data Portal, EXR)"


# First business day with euro foreign exchange reference rates (the euro was introduced
# on 1999-01-01; 1999-01-04 was the first TARGET business day).
ECB_RATES_SINCE = date(1999, 1, 4)


class ExchangeRateNotFound(LookupError):
    pass


class UnsupportedRateDate(ValueError):
    """The conversion day predates the ECB reference rates; asking the ECB makes no sense."""


def today_utc() -> date:
    return datetime.now(UTC).date()


TodayDep = Annotated[date, Depends(today_utc)]


def get_ecb_client(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[EcbClient]:
    client = EcbClient(settings.ecb_api_base_url, settings.ecb_timeout_seconds)
    try:
        yield client
    finally:
        client.close()


EcbClientDep = Annotated[EcbClient, Depends(get_ecb_client)]


def _cached(session: Session, currency: str, day: date) -> ExchangeRate | None:
    statement = select(ExchangeRate).where(
        ExchangeRate.currency == currency, ExchangeRate.rate_date == day
    )
    return session.exec(statement).first()


def _latest_cached_on_or_before(
    session: Session, currency: str, day: date, not_before: date
) -> ExchangeRate | None:
    statement = (
        select(ExchangeRate)
        .where(ExchangeRate.currency == currency)
        .where(col(ExchangeRate.rate_date).between(not_before, day))
        .order_by(col(ExchangeRate.rate_date).desc())
    )
    return session.exec(statement).first()


def _store(session: Session, currency: str, observations: list[EcbObservation]) -> None:
    """Insert observations not yet cached.

    Two requests for the same uncached day can both fetch from the ECB and race to insert the
    same rows; the unique constraint rejects the loser, which rolls back and retries once with
    the winner's rows now visible. Nothing is cached for days the ECB returned no value.
    """
    if not observations:
        return
    days = [observation.rate_date for observation in observations]
    for attempt in range(2):
        known = set(
            session.exec(
                select(col(ExchangeRate.rate_date))
                .where(ExchangeRate.currency == currency)
                .where(col(ExchangeRate.rate_date).in_(days))
            ).all()
        )
        fetched_at = datetime.now(UTC)
        for observation in observations:
            if observation.rate_date not in known:
                session.add(
                    ExchangeRate(
                        currency=currency,
                        rate_date=observation.rate_date,
                        currency_per_eur=observation.currency_per_eur,
                        fetched_at=fetched_at,
                    )
                )
        try:
            session.commit()
            return
        except IntegrityError:
            session.rollback()
            if attempt == 1:
                logger.warning(
                    "Could not cache ECB rates for %s after a concurrent insert", currency
                )


def _explain(requested: date, rate_date: date, today: date) -> tuple[FallbackReason, str]:
    closing = target_closing_reason(requested)
    fallback = (
        f"Using the latest previous ECB business day, {rate_date.isoformat()}, as CIRS "
        "art. 23.º n.º 3 prescribes (última cotação anterior)."
    )
    if closing in ("Saturday", "Sunday"):
        return FallbackReason.WEEKEND, (
            f"The ECB does not publish reference rates on weekends "
            f"({closing} {requested.isoformat()}). {fallback}"
        )
    if closing is not None:
        return FallbackReason.TARGET_HOLIDAY, (
            f"The ECB does not publish reference rates on TARGET closing days "
            f"({requested.isoformat()} is {closing}). {fallback}"
        )
    if requested >= today:
        return FallbackReason.NOT_YET_PUBLISHED, (
            f"The ECB has not published a reference rate for {requested.isoformat()} yet "
            "(rates come out around 16:00 CET on TARGET business days). Using the latest "
            f"available rate, {rate_date.isoformat()}; check again once it is published."
        )
    return FallbackReason.NO_RATE_PUBLISHED, (
        f"The ECB published no reference rate for {requested.isoformat()}. {fallback}"
    )


def _lookup(
    session: Session, ecb: EcbClient, code: str, requested: date, today: date
) -> RateLookup:
    """ECB rate for ``requested`` or, when nothing was published, the last earlier business day."""

    def result(row: ExchangeRate, *, from_cache: bool) -> RateLookup:
        is_fallback = row.rate_date != requested
        reason: FallbackReason | None = None
        if is_fallback:
            reason, note = _explain(requested, row.rate_date, today)
        else:
            note = f"ECB euro foreign exchange reference rate for {requested.isoformat()}."
        return RateLookup(
            requested_date=requested,
            rate_date=row.rate_date,
            currency_per_eur=row.currency_per_eur,
            is_fallback=is_fallback,
            fallback_reason=reason,
            note=note,
            fetched_at=row.fetched_at,
            from_cache=from_cache,
        )

    exact = _cached(session, code, requested)
    if exact is not None:
        return result(exact, from_cache=True)

    # Weekends and TARGET holidays never get a rate: serve the previous business day from the
    # cache without a round trip when we already hold it.
    if target_closing_reason(requested) is not None:
        previous = _cached(session, code, previous_target_business_day(requested))
        if previous is not None:
            return result(previous, from_cache=True)

    window_end = min(requested, today)
    window_start = window_end - timedelta(days=LOOKBACK_DAYS)
    _store(session, code, ecb.fetch_daily_rates(code, window_start, window_end))

    latest = _latest_cached_on_or_before(session, code, requested, window_start)
    if latest is None:
        raise ExchangeRateNotFound(
            f"The ECB has no {code} reference rate between {window_start.isoformat()} and "
            f"{window_end.isoformat()}"
        )
    return result(latest, from_cache=False)


def lookup_exchange_rate(
    session: Session,
    ecb: EcbClient,
    currency: Currency,
    payout_date: date,
    invoice_issued_on: date | None = None,
    today: date | None = None,
) -> ExchangeRateRead:
    """Rates converting a payout: the Fatura-Recibo rate (top level) and the IRS rate.

    The document day is chosen by :func:`conversion_date` (CIVA art. 49.º with art. 8.º n.º 1);
    the IRS day is always the payout date (CIRS art. 23.º n.º 1 al. b)). When the ECB published
    nothing on a day, the latest earlier business day is returned with an explanation. Raises
    :class:`UnsupportedRateDate` for days before the euro, :class:`ExchangeRateNotFound` when
    the ECB has nothing in the lookback window and :class:`app.ecb.EcbUnavailable` when the
    ECB Data Portal cannot be used.
    """
    if currency == Currency.EUR:
        raise ValueError("EUR has no reference rate against itself")
    today = today or today_utc()
    code = currency.value
    conversion = conversion_date(payout_date, invoice_issued_on)
    if conversion.rate_date < ECB_RATES_SINCE:
        raise UnsupportedRateDate(
            f"No ECB euro reference rates exist before {ECB_RATES_SINCE.isoformat()} "
            f"(asked for {conversion.rate_date.isoformat()})"
        )

    document = _lookup(session, ecb, code, conversion.rate_date, today)
    irs = (
        document
        if conversion.rate_date == payout_date
        else _lookup(session, ecb, code, payout_date, today)
    )
    return ExchangeRateRead(
        **document.model_dump(),
        currency=currency,
        payout_date=payout_date,
        invoice_issued_on=invoice_issued_on,
        conversion_basis=conversion.basis,
        conversion_note=conversion.explanation,
        irs=irs,
        rates_differ=irs.rate_date != document.rate_date,
        source=SOURCE,
        source_url=series_page_url(code),
        legal_basis=LEGAL_BASIS,
    )
