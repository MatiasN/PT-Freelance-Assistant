from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.fiscal.parameters import FiscalParameters, IrsBracket

CENT = Decimal("0.01")


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BracketSlice:
    lower_limit: Decimal
    upper_limit: Decimal | None
    rate: Decimal
    taxable_in_bracket: Decimal
    tax: Decimal


@dataclass(frozen=True)
class ProgressiveTax:
    taxable_income: Decimal
    total_tax: Decimal
    marginal_rate: Decimal
    effective_rate: Decimal
    slices: tuple[BracketSlice, ...]


@dataclass(frozen=True)
class IrsEstimate:
    year: int
    employment_gross: Decimal
    employment_specific_deduction: Decimal
    employment_net_income: Decimal
    freelance_gross: Decimal
    simplified_regime_coefficient: Decimal
    freelance_taxable_income: Decimal
    tax_without_freelance: ProgressiveTax
    tax_with_freelance: ProgressiveTax
    freelance_tax_impact: Decimal
    freelance_effective_rate: Decimal


def simplified_regime_taxable_income(gross: Decimal, parameters: FiscalParameters) -> Decimal:
    return to_cents(gross * parameters.simplified_regime_services_coefficient)


def employment_specific_deduction(gross: Decimal, parameters: FiscalParameters) -> Decimal:
    mandatory_contributions = gross * parameters.employee_social_security_rate
    deduction = max(parameters.category_a_specific_deduction, mandatory_contributions)
    return to_cents(min(deduction, gross))


def progressive_tax(taxable_income: Decimal, brackets: tuple[IrsBracket, ...]) -> ProgressiveTax:
    slices: list[BracketSlice] = []
    lower_limit = Decimal("0")
    total_tax = Decimal("0")
    marginal_rate = brackets[0].rate

    for bracket in brackets:
        if taxable_income <= lower_limit:
            break
        if bracket.upper_limit is None:
            top = taxable_income
        else:
            top = min(taxable_income, bracket.upper_limit)
        taxable_in_bracket = top - lower_limit
        tax = taxable_in_bracket * bracket.rate
        slices.append(
            BracketSlice(
                lower_limit,
                bracket.upper_limit,
                bracket.rate,
                to_cents(taxable_in_bracket),
                to_cents(tax),
            )
        )
        total_tax += tax
        marginal_rate = bracket.rate
        if bracket.upper_limit is not None:
            lower_limit = bracket.upper_limit

    if taxable_income > 0:
        effective_rate = (total_tax / taxable_income).quantize(Decimal("0.0001"))
    else:
        effective_rate = Decimal("0")

    return ProgressiveTax(
        taxable_income=to_cents(taxable_income),
        total_tax=to_cents(total_tax),
        marginal_rate=marginal_rate,
        effective_rate=effective_rate,
        slices=tuple(slices),
    )


def estimate_irs(
    employment_gross: Decimal, freelance_gross: Decimal, parameters: FiscalParameters
) -> IrsEstimate:
    """Single-taxpayer mainland estimate, before deduções à coleta and withholding credits."""
    deduction = employment_specific_deduction(employment_gross, parameters)
    employment_net = employment_gross - deduction
    freelance_taxable = simplified_regime_taxable_income(freelance_gross, parameters)

    without_freelance = progressive_tax(employment_net, parameters.irs_brackets)
    with_freelance = progressive_tax(employment_net + freelance_taxable, parameters.irs_brackets)
    impact = with_freelance.total_tax - without_freelance.total_tax

    if freelance_gross > 0:
        freelance_effective_rate = (impact / freelance_gross).quantize(Decimal("0.0001"))
    else:
        freelance_effective_rate = Decimal("0")

    return IrsEstimate(
        year=parameters.year,
        employment_gross=to_cents(employment_gross),
        employment_specific_deduction=deduction,
        employment_net_income=to_cents(employment_net),
        freelance_gross=to_cents(freelance_gross),
        simplified_regime_coefficient=parameters.simplified_regime_services_coefficient,
        freelance_taxable_income=freelance_taxable,
        tax_without_freelance=without_freelance,
        tax_with_freelance=with_freelance,
        freelance_tax_impact=to_cents(impact),
        freelance_effective_rate=freelance_effective_rate,
    )
