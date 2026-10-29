"""Year-specific Portuguese fiscal parameters.

Every value carries the legal source it was taken from. Values must be re-checked
against the official text each year before adding a new entry.
"""

from dataclasses import dataclass
from decimal import Decimal


class UnsupportedFiscalYear(ValueError):
    def __init__(self, year: int) -> None:
        super().__init__(f"No fiscal parameters configured for {year}")
        self.year = year


@dataclass(frozen=True)
class IrsBracket:
    upper_limit: Decimal | None
    rate: Decimal


@dataclass(frozen=True)
class FiscalParameters:
    year: int
    ias: Decimal
    irs_brackets: tuple[IrsBracket, ...]
    category_a_specific_deduction_floor: Decimal
    category_a_specific_deduction_ias_multiplier: Decimal
    employee_social_security_rate: Decimal
    simplified_regime_services_coefficient: Decimal
    independent_social_security_rate: Decimal
    independent_relevant_income_coefficient: Decimal
    independent_exemption_ias_multiplier: Decimal

    @property
    def category_a_specific_deduction(self) -> Decimal:
        by_ias = self.ias * self.category_a_specific_deduction_ias_multiplier
        return max(self.category_a_specific_deduction_floor, by_ias).quantize(Decimal("0.01"))

    @property
    def social_security_exemption_threshold(self) -> Decimal:
        return self.ias * self.independent_exemption_ias_multiplier


FISCAL_PARAMETERS: dict[int, FiscalParameters] = {
    2026: FiscalParameters(
        year=2026,
        # Portaria n.º 480-A/2025/1, de 30 de dezembro, art. 2.º
        ias=Decimal("537.13"),
        # CIRS art. 68.º, wording of Lei n.º 73-A/2025, de 30 de dezembro (mainland rates)
        irs_brackets=(
            IrsBracket(Decimal("8342"), Decimal("0.125")),
            IrsBracket(Decimal("12587"), Decimal("0.157")),
            IrsBracket(Decimal("17838"), Decimal("0.212")),
            IrsBracket(Decimal("23089"), Decimal("0.241")),
            IrsBracket(Decimal("29397"), Decimal("0.311")),
            IrsBracket(Decimal("43090"), Decimal("0.349")),
            IrsBracket(Decimal("46566"), Decimal("0.431")),
            IrsBracket(Decimal("86634"), Decimal("0.446")),
            IrsBracket(None, Decimal("0.48")),
        ),
        # CIRS art. 25.º, n.º 1, al. a) and n.º 4
        category_a_specific_deduction_floor=Decimal("4104"),
        category_a_specific_deduction_ias_multiplier=Decimal("8.54"),
        # Código Contributivo art. 53.º
        employee_social_security_rate=Decimal("0.11"),
        # CIRS art. 31.º, n.º 1, al. b) — services listed in art. 151.º table (e.g. code 1519)
        simplified_regime_services_coefficient=Decimal("0.75"),
        # Código Contributivo art. 168.º, n.º 1
        independent_social_security_rate=Decimal("0.214"),
        # Código Contributivo art. 162.º, n.º 1, al. a)
        independent_relevant_income_coefficient=Decimal("0.70"),
        # Código Contributivo art. 157.º, n.º 1, al. a) and n.º 2
        independent_exemption_ias_multiplier=Decimal("4"),
    ),
}


def get_fiscal_parameters(year: int) -> FiscalParameters:
    try:
        return FISCAL_PARAMETERS[year]
    except KeyError:
        raise UnsupportedFiscalYear(year) from None


def supported_years() -> list[int]:
    return sorted(FISCAL_PARAMETERS)
