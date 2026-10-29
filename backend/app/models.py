from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import model_validator
from sqlalchemy import Column
from sqlalchemy import Enum as SqlEnum
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.fiscal.currency_conversion import ConversionBasis


class Currency(StrEnum):
    EUR = "EUR"
    USD = "USD"


class FallbackReason(StrEnum):
    WEEKEND = "weekend"
    TARGET_HOLIDAY = "target_holiday"
    NOT_YET_PUBLISHED = "not_yet_published"
    NO_RATE_PUBLISHED = "no_rate_published"


class RateSource(StrEnum):
    MANUAL = "manual"
    ECB = "ecb"


class RatePurpose(StrEnum):
    DOCUMENT = "document"  # currency_per_eur / eur_amount (Fatura-Recibo, CIVA day)
    IRS = "irs"  # irs_currency_per_eur / irs_eur_amount (CIRS art. 23.º, payment day)


class RateProvenanceBase(SQLModel):
    """Where a stored rate came from, and what the ECB said for that day regardless.

    `source` is "ecb" when the ECB value was used as-is and "manual" when the user typed the
    rate; the `ecb_*` fields keep the ECB evidence either way (None when the lookup failed).
    """

    source: RateSource
    requested_date: date | None = None
    ecb_rate_date: date | None = None
    ecb_currency_per_eur: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=6
    )
    is_fallback: bool | None = None
    fallback_reason: FallbackReason | None = None
    fetched_at: datetime | None = None


def _enum_values(enum: type[StrEnum]) -> SqlEnum:
    """Store the API values ("ecb", "weekend"...) rather than the member names."""
    return SqlEnum(enum, values_callable=lambda members: [member.value for member in members])


class PayoutRateProvenance(RateProvenanceBase, table=True):
    """Side table (one row per pair) so that existing `payout` tables are never altered."""

    __tablename__ = "payout_rate_provenance"
    __table_args__ = (UniqueConstraint("payout_id", "purpose", name="uq_payout_rate_purpose"),)

    id: int | None = Field(default=None, primary_key=True)
    payout_id: int = Field(foreign_key="payout.id", index=True)
    purpose: RatePurpose = Field(sa_column=Column(_enum_values(RatePurpose), nullable=False))
    source: RateSource = Field(sa_column=Column(_enum_values(RateSource), nullable=False))
    fallback_reason: FallbackReason | None = Field(
        default=None, sa_column=Column(_enum_values(FallbackReason), nullable=True)
    )
    payout: "Payout" = Relationship(back_populates="provenance")


class RateProvenanceRead(RateProvenanceBase):
    purpose: RatePurpose


class PayoutBase(SQLModel):
    payout_date: date
    currency: Currency
    original_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency_per_eur: Decimal = Field(
        default=Decimal("1"),
        gt=0,
        max_digits=12,
        decimal_places=6,
        description=(
            "Rate for the Fatura-Recibo amount, ECB convention: units of `currency` for 1 EUR "
            "(e.g. 1.0850 USD). Day per CIVA art. 49.º n.º 1 with art. 8.º n.º 1: the invoice "
            "date when the invoice precedes the payout, otherwise the payout date."
        ),
    )
    rate_date: date | None = Field(
        default=None, description="ECB business day `currency_per_eur` belongs to, if known."
    )
    irs_currency_per_eur: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=6,
        description=(
            "Rate of the day the money was paid or made available (CIRS art. 23.º n.º 1 "
            "al. b)), used for the IRS income. Defaults to `currency_per_eur`."
        ),
    )
    irs_rate_date: date | None = Field(
        default=None, description="ECB business day `irs_currency_per_eur` belongs to, if known."
    )
    client_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    invoice_number: str | None = Field(default=None, max_length=50)
    invoice_issued_on: date | None = None

    @model_validator(mode="after")
    def eur_payouts_have_unit_rate(self) -> "PayoutBase":
        if self.currency == Currency.EUR and (
            self.currency_per_eur != 1 or self.irs_currency_per_eur not in (None, 1)
        ):
            raise ValueError("EUR payouts must use an exchange rate of 1")
        return self


class Payout(PayoutBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    eur_amount: Decimal = Field(max_digits=12, decimal_places=2, index=True)
    irs_currency_per_eur: Decimal = Field(gt=0, max_digits=12, decimal_places=6)
    irs_eur_amount: Decimal = Field(max_digits=12, decimal_places=2)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provenance: list[PayoutRateProvenance] = Relationship(
        back_populates="payout", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    def provenance_for(self, purpose: RatePurpose) -> PayoutRateProvenance | None:
        return next((row for row in self.provenance if row.purpose == purpose), None)


class PayoutCreate(PayoutBase):
    rate_provenance: RateProvenanceBase | None = None
    irs_rate_provenance: RateProvenanceBase | None = None


class PayoutRead(PayoutBase):
    id: int
    eur_amount: Decimal
    irs_currency_per_eur: Decimal
    irs_eur_amount: Decimal
    created_at: datetime
    # None for payouts recorded before provenance was tracked (or for EUR payouts).
    rate_provenance: RateProvenanceRead | None
    irs_rate_provenance: RateProvenanceRead | None


class ExchangeRate(SQLModel, table=True):
    """Cached ECB euro foreign exchange reference rate for one currency on one business day.

    Only published observations are stored: non-publication days (weekends, TARGET closing
    days, today before the ~16:00 CET release) are never cached, so a later lookup can still
    pick up the rate once the ECB publishes it.
    """

    __tablename__ = "exchange_rate"
    __table_args__ = (UniqueConstraint("currency", "rate_date", name="uq_exchange_rate_day"),)

    id: int | None = Field(default=None, primary_key=True)
    currency: str = Field(max_length=3, index=True)
    rate_date: date = Field(index=True)
    currency_per_eur: Decimal = Field(gt=0, max_digits=12, decimal_places=6)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RateLookup(SQLModel):
    """One resolved ECB rate: the day asked for and the business day actually published."""

    requested_date: date
    rate_date: date
    currency_per_eur: Decimal
    is_fallback: bool
    fallback_reason: FallbackReason | None
    note: str
    fetched_at: datetime
    from_cache: bool


class ExchangeRateRead(RateLookup):
    """Rate for the Fatura-Recibo (top level, CIVA day) plus the IRS rate (payment day).

    Both are the same lookup unless the invoice was issued before the payout.
    """

    currency: Currency
    payout_date: date
    invoice_issued_on: date | None
    conversion_basis: ConversionBasis
    conversion_note: str
    irs: RateLookup
    rates_differ: bool
    source: str
    source_url: str
    legal_basis: str
