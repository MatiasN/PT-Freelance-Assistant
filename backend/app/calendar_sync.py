from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from caldav.davclient import DAVClient
from caldav.lib.error import DAVError
from icalendar import Alarm, Calendar, Event, vRecur

from app.config import Settings
from app.fiscal.deadlines import Deadline

PRODUCT_ID = "-//PT Tax Assistant//pt-tax-assistant//EN"
UID_DOMAIN = "pt-tax-assistant"


class CalendarNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncReport:
    calendar_url: str
    pushed: int
    failed: list[str]


def deadline_uid(deadline: Deadline) -> str:
    return f"{deadline.key}@{UID_DOMAIN}"


def _event(deadline: Deadline, generated_at: datetime) -> Event:
    event = Event()
    event.add("uid", deadline_uid(deadline))
    event.add("dtstamp", generated_at)
    event.add("summary", deadline.title)
    event.add("dtstart", deadline.due)
    event.add("dtend", deadline.due + timedelta(days=1))
    event.add("description", deadline.description_markdown())
    event.add("categories", ["PT Tax", deadline.kind.value])
    event.add("transp", "TRANSPARENT")
    if deadline.links:
        event.add("url", deadline.links[0].url)
    if deadline.repeat_every_days is not None:
        rule = vRecur(freq="DAILY", interval=deadline.repeat_every_days)
        if deadline.repeat_until is not None:
            rule["until"] = deadline.repeat_until
        event.add("rrule", rule)

    for days_before in deadline.reminder_days_before:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", deadline.title)
        alarm.add("trigger", timedelta(days=-days_before, hours=9))
        event.add_component(alarm)
    return event


def deadline_to_ical(deadline: Deadline, generated_at: datetime | None = None) -> str:
    calendar = Calendar()
    calendar.add("prodid", PRODUCT_ID)
    calendar.add("version", "2.0")
    calendar.add_component(_event(deadline, generated_at or datetime.now(UTC)))
    return str(calendar.to_ical().decode())


def deadlines_to_ical(deadlines: list[Deadline]) -> str:
    calendar = Calendar()
    calendar.add("prodid", PRODUCT_ID)
    calendar.add("version", "2.0")
    calendar.add("x-wr-calname", "PT Tax Deadlines")
    generated_at = datetime.now(UTC)
    for deadline in deadlines:
        calendar.add_component(_event(deadline, generated_at))
    return str(calendar.to_ical().decode())


def push_deadlines(deadlines: list[Deadline], settings: Settings) -> SyncReport:
    """Upsert every deadline into the Nextcloud calendar. Stable UIDs make re-runs idempotent."""
    if not settings.caldav_configured:
        raise CalendarNotConfigured("Set PTTAX_CALDAV_CALENDAR_URL, _USERNAME and _PASSWORD")

    client = DAVClient(
        url=settings.caldav_url or settings.caldav_calendar_url,
        username=settings.caldav_username,
        password=settings.caldav_password.get_secret_value(),
        ssl_verify_cert=settings.caldav_verify_tls,
        timeout=30,
    )
    calendar = client.calendar(url=settings.caldav_calendar_url)  # type: ignore[no-untyped-call]

    pushed = 0
    failed: list[str] = []
    for deadline in deadlines:
        try:
            calendar.add_event(ical=deadline_to_ical(deadline))
            pushed += 1
        except (DAVError, OSError) as error:
            failed.append(f"{deadline.key}: {error}")
    return SyncReport(calendar_url=settings.caldav_calendar_url, pushed=pushed, failed=failed)
