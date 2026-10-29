import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.fiscal.irs import to_cents
from app.fiscal.parameters import FiscalParameters


@dataclass(frozen=True)
class QuarterlySocialSecurity:
    year: int
    quarter: int
    services_income: Decimal
    relevant_income: Decimal
    monthly_average_relevant_income: Decimal
    exempt_threshold: Decimal
    monthly_contribution_base: Decimal
    monthly_contribution: Decimal
    quarterly_contribution: Decimal
    declaration_deadline: date
    contribution_months: tuple[date, date, date]


def quarter_of(day: date) -> int:
    return (day.month - 1) // 3 + 1


def quarter_months(quarter: int) -> tuple[int, int, int]:
    first = (quarter - 1) * 3 + 1
    return first, first + 1, first + 2


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    return date(day.year + month_index // 12, month_index % 12 + 1, 1)


def declaration_deadline(year: int, quarter: int) -> date:
    """Quarterly declaration is due by the end of the month after the quarter closes."""
    declaration_month = _add_months(date(year, quarter_months(quarter)[2], 1), 1)
    last_day = calendar.monthrange(declaration_month.year, declaration_month.month)[1]
    return declaration_month.replace(day=last_day)


def estimate_quarter(
    year: int,
    quarter: int,
    services_income: Decimal,
    parameters: FiscalParameters,
    *,
    accumulates_with_employment: bool = True,
) -> QuarterlySocialSecurity:
    """Contributions set by one quarterly declaration (Código Contributivo arts. 157.º-168.º).

    With concurrent employment, relevant income up to 4×IAS per month is exempt and only
    the excess is subject to contributions.
    """
    relevant_income = services_income * parameters.independent_relevant_income_coefficient
    monthly_average = relevant_income / 3

    if accumulates_with_employment:
        exempt_threshold = parameters.social_security_exemption_threshold
    else:
        exempt_threshold = Decimal("0")

    monthly_base = max(Decimal("0"), monthly_average - exempt_threshold)
    monthly_contribution = to_cents(monthly_base * parameters.independent_social_security_rate)

    deadline = declaration_deadline(year, quarter)
    first_contribution_month = _add_months(deadline, 1)

    return QuarterlySocialSecurity(
        year=year,
        quarter=quarter,
        services_income=to_cents(services_income),
        relevant_income=to_cents(relevant_income),
        monthly_average_relevant_income=to_cents(monthly_average),
        exempt_threshold=to_cents(exempt_threshold),
        monthly_contribution_base=to_cents(monthly_base),
        monthly_contribution=monthly_contribution,
        quarterly_contribution=monthly_contribution * 3,
        declaration_deadline=deadline,
        contribution_months=(
            first_contribution_month,
            _add_months(first_contribution_month, 1),
            _add_months(first_contribution_month, 2),
        ),
    )
