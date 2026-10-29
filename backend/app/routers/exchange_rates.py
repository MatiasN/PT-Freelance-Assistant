from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.db import get_session
from app.exchange_rates import (
    EcbClientDep,
    ExchangeRateNotFound,
    TodayDep,
    UnsupportedRateDate,
    lookup_exchange_rate,
)
from app.models import Currency, ExchangeRateRead

router = APIRouter(prefix="/api/exchange-rates", tags=["exchange-rates"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "",
    response_model=ExchangeRateRead,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No ECB rate in the lookback window"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Day before 1999-01-04 or EUR"},
        status.HTTP_502_BAD_GATEWAY: {"description": "ECB Data Portal unavailable"},
    },
)
def exchange_rate(
    session: SessionDep,
    ecb: EcbClientDep,
    today: TodayDep,
    currency: Annotated[Currency, Query(description="Foreign currency, e.g. USD")],
    payout_date: Annotated[date | None, Query(description="Day the money was received")] = None,
    on: Annotated[
        date | None, Query(alias="date", description="Same as `payout_date` (shorter form)")
    ] = None,
    invoice_issued_on: Annotated[
        date | None,
        Query(description="Day the Fatura/Fatura-Recibo was issued, if already issued"),
    ] = None,
) -> ExchangeRateRead:
    """ECB euro reference rate (units of `currency` per 1 EUR) converting a payout.

    The day is the payout date, or the invoice date when the invoice was issued before the
    payout (CIVA art. 49.º n.º 1 with art. 8.º n.º 1; CIRS art. 23.º). Non-publication days
    fall back to the previous business day. Upstream failures are reported as 502.
    """
    if currency == Currency.EUR:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "EUR needs no exchange rate (1 EUR = 1 EUR)"
        )
    if payout_date is None and on is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pass `date` or `payout_date`")
    if payout_date is not None and on is not None and payout_date != on:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "`date` and `payout_date` disagree"
        )
    payout_date = payout_date or on
    assert payout_date is not None  # narrowed by the checks above
    try:
        return lookup_exchange_rate(
            session, ecb, currency, payout_date, invoice_issued_on, today=today
        )
    except UnsupportedRateDate as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    except ExchangeRateNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
