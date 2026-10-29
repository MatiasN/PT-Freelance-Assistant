from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, col, select

from app.config import Settings, get_settings
from app.db import get_session
from app.fiscal.invoice_text import PortalField, build_invoice_fields
from app.fiscal.irs import to_cents
from app.models import Payout, PayoutCreate, PayoutRead

router = APIRouter(prefix="/api/payouts", tags=["payouts"])

SessionDep = Annotated[Session, Depends(get_session)]


def _get_payout_or_404(session: Session, payout_id: int) -> Payout:
    payout = session.get(Payout, payout_id)
    if payout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payout not found")
    return payout


def _apply(payout: Payout, data: PayoutCreate) -> None:
    for field_name, value in data.model_dump().items():
        setattr(payout, field_name, value)
    payout.eur_amount = to_cents(data.original_amount / data.currency_per_eur)


@router.get("", response_model=list[PayoutRead])
def list_payouts(
    session: SessionDep, year: Annotated[int | None, Query(ge=2000, le=2100)] = None
) -> list[Payout]:
    query = select(Payout).order_by(col(Payout.payout_date).desc(), col(Payout.id).desc())
    if year is not None:
        query = query.where(col(Payout.payout_date).between(date(year, 1, 1), date(year, 12, 31)))
    return list(session.exec(query).all())


@router.post("", response_model=PayoutRead, status_code=status.HTTP_201_CREATED)
def create_payout(data: PayoutCreate, session: SessionDep) -> Payout:
    payout = Payout.model_validate(data, update={"eur_amount": 0})
    _apply(payout, data)
    session.add(payout)
    session.commit()
    session.refresh(payout)
    return payout


@router.put("/{payout_id}", response_model=PayoutRead)
def update_payout(payout_id: int, data: PayoutCreate, session: SessionDep) -> Payout:
    payout = _get_payout_or_404(session, payout_id)
    _apply(payout, data)
    session.add(payout)
    session.commit()
    session.refresh(payout)
    return payout


@router.delete("/{payout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payout(payout_id: int, session: SessionDep) -> None:
    session.delete(_get_payout_or_404(session, payout_id))
    session.commit()


@router.get("/{payout_id}/invoice-fields")
def invoice_fields(
    payout_id: int, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> list[PortalField]:
    return build_invoice_fields(_get_payout_or_404(session, payout_id), settings)
