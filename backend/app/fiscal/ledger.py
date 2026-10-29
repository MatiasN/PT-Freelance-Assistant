from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.fiscal.irs import IrsEstimate, estimate_irs, to_cents
from app.fiscal.parameters import FiscalParameters
from app.fiscal.social_security import QuarterlySocialSecurity, estimate_quarter, quarter_of


@dataclass(frozen=True)
class IncomeEntry:
    day: date
    eur_amount: Decimal


@dataclass(frozen=True)
class PeriodTotal:
    label: str
    gross: Decimal
    savings_target: Decimal


@dataclass(frozen=True)
class YearOverview:
    year: int
    gross: Decimal
    savings_pool_rate: Decimal
    savings_target: Decimal
    irs: IrsEstimate
    social_security_quarters: tuple[QuarterlySocialSecurity, ...]
    social_security_total: Decimal
    estimated_obligations: Decimal
    expected_net: Decimal
    savings_gap: Decimal
    monthly: tuple[PeriodTotal, ...]
    weekly: tuple[PeriodTotal, ...]


def _period_total(label: str, gross: Decimal, savings_rate: Decimal) -> PeriodTotal:
    return PeriodTotal(
        label=label, gross=to_cents(gross), savings_target=to_cents(gross * savings_rate)
    )


def build_year_overview(
    year: int,
    entries: Iterable[IncomeEntry],
    *,
    employment_gross: Decimal,
    savings_pool_rate: Decimal,
    parameters: FiscalParameters,
) -> YearOverview:
    entries_in_year = [entry for entry in entries if entry.day.year == year]

    monthly_gross = {month: Decimal("0") for month in range(1, 13)}
    weekly_gross: dict[str, Decimal] = {}
    quarterly_gross = {quarter: Decimal("0") for quarter in range(1, 5)}
    for entry in entries_in_year:
        monthly_gross[entry.day.month] += entry.eur_amount
        quarterly_gross[quarter_of(entry.day)] += entry.eur_amount
        iso_year, iso_week, _ = entry.day.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
        weekly_gross[week_label] = weekly_gross.get(week_label, Decimal("0")) + entry.eur_amount

    gross = sum(monthly_gross.values(), Decimal("0"))
    irs = estimate_irs(employment_gross, gross, parameters)
    quarters = tuple(
        estimate_quarter(year, quarter, quarterly_gross[quarter], parameters)
        for quarter in range(1, 5)
    )
    social_security_total = sum((q.quarterly_contribution for q in quarters), Decimal("0"))
    obligations = irs.freelance_tax_impact + social_security_total
    savings_target = to_cents(gross * savings_pool_rate)

    return YearOverview(
        year=year,
        gross=to_cents(gross),
        savings_pool_rate=savings_pool_rate,
        savings_target=savings_target,
        irs=irs,
        social_security_quarters=quarters,
        social_security_total=social_security_total,
        estimated_obligations=obligations,
        expected_net=to_cents(gross - obligations),
        savings_gap=to_cents(obligations - savings_target),
        monthly=tuple(
            _period_total(f"{year}-{month:02d}", amount, savings_pool_rate)
            for month, amount in monthly_gross.items()
        ),
        weekly=tuple(
            _period_total(label, amount, savings_pool_rate)
            for label, amount in sorted(weekly_gross.items())
        ),
    )
