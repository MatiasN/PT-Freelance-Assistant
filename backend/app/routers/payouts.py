from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, col, select

from app.config import Settings, get_settings
from app.db import get_session
from app.fiscal.invoice_text import PortalField, build_invoice_fields
from app.fiscal.irs import to_cents
from app.models import (
    Payout,
    PayoutCreate,
    PayoutRateProvenance,
    PayoutRead,
    RateProvenanceRead,
    RatePurpose,
)

router = APIRouter(prefix="/api/payouts", tags=["payouts"])

SessionDep = Annotated[Session, Depends(get_session)]


def _get_payout_or_404(session: Session, payout_id: int) -> Payout:
    payout = session.get(Payout, payout_id)
    if payout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payout not found")
    return payout


PROVENANCE_FIELDS = {"rate_provenance", "irs_rate_provenance"}


def _apply(session: Session, payout: Payout, data: PayoutCreate) -> None:
    for field_name, value in data.model_dump(exclude=PROVENANCE_FIELDS).items():
        setattr(payout, field_name, value)
    # Fatura-Recibo amount (CIVA art. 49.º day) and IRS income (CIRS art. 23.º, payment day).
    payout.eur_amount = to_cents(data.original_amount / data.currency_per_eur)
    payout.irs_currency_per_eur = data.irs_currency_per_eur or data.currency_per_eur
    payout.irs_eur_amount = to_cents(data.original_amount / payout.irs_currency_per_eur)
    if payout.provenance:
        payout.provenance.clear()
        session.flush()  # delete the old rows before inserting (unique payout_id + purpose)
    payout.provenance = [  # payout_id is filled in by the relationship on flush
        PayoutRateProvenance(**provenance.model_dump(), purpose=purpose)
        for purpose, provenance in (
            (RatePurpose.DOCUMENT, data.rate_provenance),
            (RatePurpose.IRS, data.irs_rate_provenance),
        )
        if provenance is not None
    ]


def _read(payout: Payout) -> PayoutRead:
    def provenance(purpose: RatePurpose) -> RateProvenanceRead | None:
        row = payout.provenance_for(purpose)
        return None if row is None else RateProvenanceRead.model_validate(row)

    return PayoutRead.model_validate(
        payout,
        update={
            "rate_provenance": provenance(RatePurpose.DOCUMENT),
            "irs_rate_provenance": provenance(RatePurpose.IRS),
        },
    )


@router.get("")
def list_payouts(
    session: SessionDep, year: Annotated[int | None, Query(ge=2000, le=2100)] = None
) -> list[PayoutRead]:
    query = select(Payout).order_by(col(Payout.payout_date).desc(), col(Payout.id).desc())
    if year is not None:
        query = query.where(col(Payout.payout_date).between(date(year, 1, 1), date(year, 12, 31)))
    return [_read(payout) for payout in session.exec(query).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_payout(data: PayoutCreate, session: SessionDep) -> PayoutRead:
    payout = Payout.model_validate(
        data,
        update={
            "eur_amount": 0,
            "irs_eur_amount": 0,
            "irs_currency_per_eur": data.irs_currency_per_eur or data.currency_per_eur,
        },
    )
    _apply(session, payout, data)
    session.add(payout)
    session.commit()
    session.refresh(payout)
    return _read(payout)


@router.put("/{payout_id}")
def update_payout(payout_id: int, data: PayoutCreate, session: SessionDep) -> PayoutRead:
    payout = _get_payout_or_404(session, payout_id)
    _apply(session, payout, data)
    session.add(payout)
    session.commit()
    session.refresh(payout)
    return _read(payout)


@router.delete("/{payout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payout(payout_id: int, session: SessionDep) -> None:
    session.delete(_get_payout_or_404(session, payout_id))
    session.commit()


@router.get("/{payout_id}/invoice-fields")
def invoice_fields(
    payout_id: int, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> list[PortalField]:
    return build_invoice_fields(_get_payout_or_404(session, payout_id), settings)
