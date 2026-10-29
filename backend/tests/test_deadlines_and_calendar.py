from datetime import date

from icalendar import Calendar

from app.calendar_sync import deadline_to_ical, deadlines_to_ical
from app.config import VatRegime
from app.fiscal.deadlines import DeadlineKind, fiscal_deadlines


def _deadlines(vat_regime=VatRegime.QUARTERLY):
    return fiscal_deadlines(2026, vat_regime=vat_regime, viactt_interval_days=30)


def test_includes_quarterly_social_security_declarations():
    declarations = [d for d in _deadlines() if d.kind == DeadlineKind.SOCIAL_SECURITY_DECLARATION]

    assert [d.due for d in declarations] == [
        date(2026, 1, 31),
        date(2026, 4, 30),
        date(2026, 7, 31),
        date(2026, 10, 31),
    ]


def test_vat_deadlines_only_for_quarterly_regime():
    exempt = _deadlines(VatRegime.EXEMPT_ARTICLE_53)

    assert not [d for d in exempt if d.kind == DeadlineKind.VAT_DECLARATION]
    assert len([d for d in _deadlines() if d.kind == DeadlineKind.VAT_DECLARATION]) == 4


def test_deadline_keys_are_unique():
    keys = [d.key for d in _deadlines()]

    assert len(keys) == len(set(keys))


def test_every_deadline_has_guide_and_official_link():
    for deadline in _deadlines():
        assert deadline.links
        assert "https://" in deadline.description_markdown()


def test_ical_event_has_stable_uid_and_alarms():
    deadline = _deadlines()[0]
    event = Calendar.from_ical(deadline_to_ical(deadline)).walk("VEVENT")[0]

    assert str(event["uid"]) == f"{deadline.key}@pt-tax-assistant"
    assert len(event.walk("VALARM")) == len(deadline.reminder_days_before)


def test_viactt_reminder_recurs():
    calendar = Calendar.from_ical(deadlines_to_ical(_deadlines()))
    viactt = [e for e in calendar.walk("VEVENT") if str(e["uid"]).startswith("viactt-")][0]

    assert viactt["rrule"]["INTERVAL"] == [30]
