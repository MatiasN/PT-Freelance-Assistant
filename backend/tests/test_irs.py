from decimal import Decimal

from app.fiscal.irs import employment_specific_deduction, estimate_irs, progressive_tax


def test_progressive_tax_matches_official_average_rate_at_bracket_boundary(parameters_2026):
    result = progressive_tax(Decimal("17838"), parameters_2026.irs_brackets)

    assert result.total_tax == Decimal("2822.43")
    assert result.marginal_rate == Decimal("0.212")


def test_progressive_tax_spans_multiple_brackets(parameters_2026):
    result = progressive_tax(Decimal("20000"), parameters_2026.irs_brackets)

    assert result.total_tax == Decimal("3343.47")
    assert len(result.slices) == 4


def test_zero_income_has_no_tax(parameters_2026):
    result = progressive_tax(Decimal("0"), parameters_2026.irs_brackets)

    assert result.total_tax == Decimal("0.00")
    assert result.effective_rate == Decimal("0")


def test_top_bracket_is_unbounded(parameters_2026):
    result = progressive_tax(Decimal("100000"), parameters_2026.irs_brackets)

    assert result.marginal_rate == Decimal("0.48")
    assert result.slices[-1].upper_limit is None


def test_specific_deduction_uses_social_security_when_higher(parameters_2026):
    assert employment_specific_deduction(Decimal("42000"), parameters_2026) == Decimal("4620.00")


def test_specific_deduction_uses_ias_floor_for_low_salaries(parameters_2026):
    assert employment_specific_deduction(Decimal("20000"), parameters_2026) == Decimal("4587.09")


def test_freelance_impact_uses_75_percent_simplified_base(parameters_2026):
    estimate = estimate_irs(Decimal("42000"), Decimal("20000"), parameters_2026)

    assert estimate.freelance_taxable_income == Decimal("15000.00")
    assert estimate.tax_with_freelance.taxable_income == Decimal("52380.00")
    assert estimate.freelance_tax_impact == (
        estimate.tax_with_freelance.total_tax - estimate.tax_without_freelance.total_tax
    )
    assert estimate.freelance_effective_rate > Decimal("0.25")
