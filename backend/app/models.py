from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import model_validator
from sqlmodel import Field, SQLModel


class Currency(StrEnum):
    EUR = "EUR"
    USD = "USD"


class PayoutBase(SQLModel):
    payout_date: date
    currency: Currency
    original_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency_per_eur: Decimal = Field(
        default=Decimal("1"),
        gt=0,
        max_digits=12,
        decimal_places=6,
        description="ECB convention: units of `currency` for 1 EUR (e.g. 1.0850 USD).",
    )
    client_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    invoice_number: str | None = Field(default=None, max_length=50)
    invoice_issued_on: date | None = None

    @model_validator(mode="after")
    def eur_payouts_have_unit_rate(self) -> "PayoutBase":
        if self.currency == Currency.EUR and self.currency_per_eur != 1:
            raise ValueError("EUR payouts must use an exchange rate of 1")
        return self


class Payout(PayoutBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    eur_amount: Decimal = Field(max_digits=12, decimal_places=2, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PayoutCreate(PayoutBase):
    pass


class PayoutRead(PayoutBase):
    id: int
    eur_amount: Decimal
    created_at: datetime
