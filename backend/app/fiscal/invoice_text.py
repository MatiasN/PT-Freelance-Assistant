from dataclasses import dataclass
from decimal import Decimal

from app.config import Settings
from app.models import Currency, Payout


@dataclass(frozen=True)
class PortalField:
    portal_label: str
    value: str
    hint: str = ""


def format_eur(amount: Decimal) -> str:
    whole, cents = f"{amount:.2f}".split(".")
    grouped = f"{int(whole):,}".replace(",", ".")
    return f"{grouped},{cents}"


def format_rate(rate: Decimal) -> str:
    return f"{rate:.4f}".replace(".", ",")


def build_invoice_fields(payout: Payout, settings: Settings) -> list[PortalField]:
    """Values to type into Portal das Finanças → Faturas e Recibos Verdes → Emitir Fatura-Recibo."""
    client_name = payout.client_name or settings.client_name
    description = settings.service_description
    if payout.currency != Currency.EUR:
        description += (
            f" — {payout.currency.value} {payout.original_amount:.2f}"
            f" à taxa de câmbio {format_rate(payout.currency_per_eur)} {payout.currency.value}/EUR"
        )

    return [
        PortalField("Tipo de documento", "Fatura-Recibo"),
        PortalField("Data da prestação do serviço", payout.payout_date.strftime("%d/%m/%Y")),
        PortalField("País do adquirente", settings.client_country),
        PortalField("Nome do adquirente", client_name),
        PortalField(
            "NIF do adquirente",
            settings.client_tax_id,
            "Foreign client: leave the Portuguese NIF empty and fill the foreign tax id field.",
        ),
        PortalField("Morada do adquirente", settings.client_address),
        PortalField("Descrição", description),
        PortalField("Valor base (EUR)", format_eur(payout.eur_amount)),
        PortalField("Regime de IVA", settings.vat_exemption_reason, settings.vat_exemption_code),
        PortalField("Retenção na fonte de IRS", settings.withholding_option),
        PortalField("Imposto do Selo", "Não aplicável"),
        PortalField("Importância recebida (EUR)", format_eur(payout.eur_amount)),
    ]
