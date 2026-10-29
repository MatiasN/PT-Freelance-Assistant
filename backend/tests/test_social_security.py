from datetime import date
from decimal import Decimal

from app.fiscal.social_security import declaration_deadline, estimate_quarter


def test_income_below_four_ias_is_exempt_when_employed(parameters_2026):
    result = estimate_quarter(2026, 1, Decimal("9000"), parameters_2026)

    assert result.monthly_average_relevant_income == Decimal("2100.00")
    assert result.exempt_threshold == Decimal("2148.52")
    assert result.monthly_contribution == Decimal("0.00")


def test_only_the_excess_over_four_ias_is_charged(parameters_2026):
    result = estimate_quarter(2026, 1, Decimal("15000"), parameters_2026)

    assert result.monthly_contribution_base == Decimal("1351.48")
    assert result.monthly_contribution == Decimal("289.22")
    assert result.quarterly_contribution == Decimal("867.66")


def test_without_employment_all_relevant_income_is_charged(parameters_2026):
    result = estimate_quarter(
        2026, 1, Decimal("15000"), parameters_2026, accumulates_with_employment=False
    )

    assert result.monthly_contribution == Decimal("749.00")


def test_contributions_start_the_month_after_the_declaration(parameters_2026):
    result = estimate_quarter(2026, 4, Decimal("15000"), parameters_2026)

    assert result.declaration_deadline == date(2027, 1, 31)
    assert result.contribution_months[0] == date(2027, 2, 1)


def test_declaration_deadlines_fall_on_last_day_of_following_month():
    assert declaration_deadline(2026, 1) == date(2026, 4, 30)
    assert declaration_deadline(2026, 2) == date(2026, 7, 31)
    assert declaration_deadline(2026, 3) == date(2026, 10, 31)
