"""Which day's exchange rate converts a foreign-currency payout into the EUR amount of the
Fatura-Recibo.

Two codes apply, and they agree in the normal Stripe flow (money arrives, then the
Fatura-Recibo is issued for the amount received):

* **CIVA art. 49.º n.º 1** (*Conversão de valores expressos em moeda estrangeira*): amounts in a
  foreign currency are converted at the selling rate published by Banco de Portugal (which
  republishes the ECB reference rates) for the day the tax becomes chargeable. n.º 2 allows
  opting for the rate of the first business day of that month instead (not implemented here).
* **CIVA art. 8.º n.º 1** fixes that day: al. a) the invoice date when the invoice is issued
  within the deadline of art. 36.º n.º 1; al. c) *"se a transmissão de bens ou a prestação de
  serviços derem lugar ao pagamento, ainda que parcial, anteriormente à emissão da fatura, no
  momento do recebimento desse pagamento, pelo montante recebido"*.
* **CIRS art. 23.º n.º 1 al. b)** (*Valores fixados em moeda sem curso legal em Portugal*), for
  the income itself: *"tratando-se de rendimentos provenientes do exterior, aplica-se o câmbio
  de compra na data em que aqueles foram pagos ou postos à disposição do sujeito passivo"*.
  n.º 3: when no quotation exists for that day, the last previous quotation applies.

Hence: payout before (or without) an invoice -> the payout date, under both codes. Invoice
issued before the payout -> the invoice date for the document (CIVA), while IRS still looks at
the payment date; the explanation flags that discrepancy for the accountant.

Sources (verify the current wording):
https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/civa_rep/Pages/iva49.aspx
https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/civa_rep/Pages/iva8.aspx
https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/cirs_rep/Pages/irs23.aspx
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ConversionBasis(StrEnum):
    PAYOUT_DATE = "payout_date"
    INVOICE_DATE = "invoice_date"


@dataclass(frozen=True)
class ConversionDate:
    rate_date: date
    basis: ConversionBasis
    explanation: str


LEGAL_BASIS = (
    "CIVA art. 49.º n.º 1 (rate of the day the tax becomes chargeable) with art. 8.º n.º 1: "
    "al. c) payment received before the invoice -> day of receipt; al. a) invoice issued first "
    "-> invoice date. CIRS art. 23.º n.º 1 al. b): income from abroad is converted on the day "
    "it was paid or made available; n.º 3: without a quotation for that day, the last previous "
    "quotation applies."
)


def conversion_date(payout_date: date, invoice_issued_on: date | None = None) -> ConversionDate:
    """Day whose ECB reference rate converts the payout for the Fatura-Recibo."""
    if invoice_issued_on is not None and invoice_issued_on < payout_date:
        return ConversionDate(
            rate_date=invoice_issued_on,
            basis=ConversionBasis.INVOICE_DATE,
            explanation=(
                f"The invoice was issued on {invoice_issued_on.isoformat()}, before the payout "
                f"of {payout_date.isoformat()}: IVA became chargeable on the invoice date "
                "(CIVA art. 8.º n.º 1 al. a)), so the document is converted at that day's rate "
                "(CIVA art. 49.º n.º 1). For IRS, CIRS art. 23.º n.º 1 al. b) uses the day the "
                f"income was paid ({payout_date.isoformat()}); tell your accountant if the two "
                "amounts differ."
            ),
        )
    return ConversionDate(
        rate_date=payout_date,
        basis=ConversionBasis.PAYOUT_DATE,
        explanation=(
            f"Payment received on {payout_date.isoformat()}"
            + (
                f", before the invoice of {invoice_issued_on.isoformat()}"
                if invoice_issued_on is not None and invoice_issued_on > payout_date
                else ""
            )
            + ": IVA became chargeable on receipt (CIVA art. 8.º n.º 1 al. c)), and CIRS "
            "art. 23.º n.º 1 al. b) converts income on the day it was paid or made available, "
            "so both rules point to the payout date."
        ),
    )
