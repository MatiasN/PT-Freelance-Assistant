from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, select

from app.config import Settings, get_settings
from app.db import get_session
from app.fiscal.irs import IrsEstimate, estimate_irs
from app.fiscal.ledger import IncomeEntry, YearOverview, build_year_overview
from app.fiscal.parameters import FiscalParameters, get_fiscal_parameters, supported_years
from app.fiscal.social_security import QuarterlySocialSecurity, estimate_quarter
from app.models import Payout

router = APIRouter(prefix="/api", tags=["estimates"])

YearQuery = Annotated[int, Query(ge=2000, le=2100)]
MoneyQuery = Annotated[Decimal, Query(ge=0, le=10_000_000)]


def annual_employment_gross(settings: Settings) -> Decimal:
    return settings.employment_monthly_gross_salary * settings.employment_payments_per_year


@router.get("/fiscal-parameters")
def fiscal_parameters(year: YearQuery) -> FiscalParameters:
    return get_fiscal_parameters(year)


@router.get("/fiscal-parameters/years")
def fiscal_years() -> list[int]:
    return supported_years()


@router.get("/dashboard")
def dashboard(
    year: YearQuery,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> YearOverview:
    parameters = get_fiscal_parameters(year)
    in_year = col(Payout.payout_date).between(date(year, 1, 1), date(year, 12, 31))
    payouts = session.exec(select(Payout).where(in_year)).all()
    return build_year_overview(
        year,
        (IncomeEntry(payout.payout_date, payout.eur_amount) for payout in payouts),
        employment_gross=annual_employment_gross(settings),
        savings_pool_rate=settings.savings_pool_rate,
        parameters=parameters,
    )


@router.get("/estimates/irs")
def irs_estimate(
    year: YearQuery,
    freelance_gross: MoneyQuery,
    settings: Annotated[Settings, Depends(get_settings)],
    employment_gross: MoneyQuery | None = None,
) -> IrsEstimate:
    if employment_gross is None:
        employment_gross = annual_employment_gross(settings)
    return estimate_irs(employment_gross, freelance_gross, get_fiscal_parameters(year))


@router.get("/estimates/social-security")
def social_security_estimate(
    year: YearQuery,
    quarter: Annotated[int, Query(ge=1, le=4)],
    services_income: MoneyQuery,
    accumulates_with_employment: bool = True,
) -> QuarterlySocialSecurity:
    return estimate_quarter(
        year,
        quarter,
        services_income,
        get_fiscal_parameters(year),
        accumulates_with_employment=accumulates_with_employment,
    )
