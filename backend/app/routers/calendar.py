from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.calendar_sync import CalendarNotConfigured, SyncReport, deadlines_to_ical, push_deadlines
from app.config import Settings, get_settings
from app.fiscal.deadlines import Deadline, fiscal_deadlines

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

YearQuery = Annotated[int, Query(ge=2000, le=2100)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _deadlines(year: int, settings: Settings) -> list[Deadline]:
    return fiscal_deadlines(
        year,
        vat_regime=settings.vat_regime,
        viactt_interval_days=settings.viactt_reminder_interval_days,
    )


@router.get("/deadlines")
def list_deadlines(year: YearQuery, settings: SettingsDep) -> list[Deadline]:
    return _deadlines(year, settings)


@router.get("/deadlines.ics")
def download_deadlines(year: YearQuery, settings: SettingsDep) -> Response:
    return Response(
        content=deadlines_to_ical(_deadlines(year, settings)),
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="pt-tax-deadlines-{year}.ics"'},
    )


@router.get("/status")
def calendar_status(settings: SettingsDep) -> dict[str, bool | str]:
    return {"configured": settings.caldav_configured, "calendar_url": settings.caldav_calendar_url}


@router.post("/sync")
def sync_calendar(year: YearQuery, settings: SettingsDep) -> SyncReport:
    try:
        return push_deadlines(_deadlines(year, settings), settings)
    except CalendarNotConfigured as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
