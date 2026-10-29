from datetime import date
from decimal import Decimal

import httpx2 as httpx
import pytest
from sqlmodel import Session, select

from app.config import Settings
from app.ecb import (
    EcbUnavailable,
    easter_sunday,
    parse_csv_observations,
    previous_target_business_day,
    series_key,
    target_closing_reason,
)
from app.exchange_rates import (
    ExchangeRateNotFound,
    UnsupportedRateDate,
    get_ecb_client,
    lookup_exchange_rate,
    today_utc,
)
from app.fiscal.currency_conversion import ConversionBasis, conversion_date
from app.main import app
from app.models import Currency, ExchangeRate

FRIDAY = "2026-03-06"
SATURDAY = "2026-03-07"


def get_rate(client, payout_date: str, currency: str = "USD", invoice_issued_on: str | None = None):
    params = {"currency": currency, "payout_date": payout_date}
    if invoice_issued_on is not None:
        params["invoice_issued_on"] = invoice_issued_on
    return client.get("/api/exchange-rates", params=params)


def freeze_today(day: str) -> None:
    """Pin the server's notion of 'today' to the day the user is sitting at in the scenario.

    Each test sets it to fit its own story (the closure day itself, the next business day,
    before/after the 16:00 CET publication...), so nothing depends on the real clock. The
    override is cleared with the others by the `client` fixture.
    """
    app.dependency_overrides[today_utc] = lambda: date.fromisoformat(day)


def without_days(fake_ecb, *days: str) -> None:
    """Drop observations from the fake ECB, e.g. to simulate a rate not published yet."""
    fake_ecb.csv_body = "\n".join(
        line for line in fake_ecb.csv_body.splitlines() if not any(day in line for day in days)
    )


# --- endpoint -------------------------------------------------------------------------------


def test_business_day_returns_exact_ecb_rate(client, fake_ecb):
    freeze_today("2026-03-09")  # Monday: recording last Friday's payout

    response = get_rate(client, FRIDAY)

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert body["payout_date"] == FRIDAY
    assert body["invoice_issued_on"] is None
    assert body["requested_date"] == FRIDAY
    assert body["conversion_basis"] == "payout_date"
    assert "CIVA art. 8.º n.º 1 al. c)" in body["conversion_note"]
    assert "CIRS art. 23.º n.º 1 al. b)" in body["conversion_note"]
    assert body["rate_date"] == FRIDAY
    assert Decimal(body["currency_per_eur"]) == Decimal("1.0817")
    assert body["is_fallback"] is False
    assert body["fallback_reason"] is None
    assert body["from_cache"] is False
    assert "European Central Bank" in body["source"]
    assert body["source_url"].endswith("EXR.D.USD.EUR.SP00.A")
    assert "CIRS art. 23.º" in body["legal_basis"]
    assert "CIVA art. 49.º" in body["legal_basis"]
    assert "art. 8.º" in body["legal_basis"]
    assert len(fake_ecb.requests) == 1


def test_date_is_accepted_as_the_payout_day(client, fake_ecb):
    freeze_today("2026-03-09")

    body = client.get("/api/exchange-rates", params={"currency": "USD", "date": SATURDAY}).json()

    assert body["payout_date"] == SATURDAY
    assert body["rate_date"] == FRIDAY
    assert body["is_fallback"] is True
    assert body["fallback_reason"] == "weekend"
    assert "European Central Bank" in body["source"]


@pytest.mark.parametrize(
    "params",
    [
        {"currency": "USD"},
        {"currency": "USD", "date": FRIDAY, "payout_date": SATURDAY},
    ],
)
def test_missing_or_conflicting_day_is_rejected_without_http(client, fake_ecb, params):
    response = client.get("/api/exchange-rates", params=params)

    assert response.status_code == 422
    assert fake_ecb.requests == []


def test_request_follows_ecb_data_portal_api(client, fake_ecb):
    freeze_today("2026-03-09")  # Monday: the window must end on the payout day, not today

    get_rate(client, FRIDAY)

    request = fake_ecb.requests[0]
    assert request.method == "GET"
    assert request.url.host == "ecb.test"
    assert request.url.path == f"/service/data/EXR/{series_key('USD')}"
    assert request.url.params["format"] == "csvdata"
    assert request.url.params["detail"] == "dataonly"
    assert request.url.params["endPeriod"] == FRIDAY
    assert request.url.params["startPeriod"] == "2026-02-20"
    assert request.headers["accept"] == "text/csv"
    assert request.headers["user-agent"].startswith("pt-tax-assistant")


def test_second_lookup_is_served_from_cache_without_http(client, fake_ecb):
    freeze_today("2026-03-09")
    get_rate(client, FRIDAY)

    body = get_rate(client, FRIDAY).json()

    assert body["from_cache"] is True
    assert Decimal(body["currency_per_eur"]) == Decimal("1.0817")
    assert len(fake_ecb.requests) == 1


def test_weekend_falls_back_to_friday_and_explains_it(client):
    freeze_today(SATURDAY)  # recording a Saturday payout on the Saturday itself

    body = get_rate(client, SATURDAY).json()

    assert body["requested_date"] == SATURDAY
    assert body["rate_date"] == FRIDAY
    assert body["is_fallback"] is True
    assert body["fallback_reason"] == "weekend"
    assert "Saturday 2026-03-07" in body["note"]
    assert FRIDAY in body["note"]
    assert "CIRS art. 23.º n.º 3" in body["note"]


def test_weekend_uses_cached_friday_without_http(client, fake_ecb):
    freeze_today("2026-03-08")  # Sunday: Friday's payout was entered first, now Sunday's
    get_rate(client, FRIDAY)

    body = get_rate(client, "2026-03-08").json()

    assert body["rate_date"] == FRIDAY
    assert body["fallback_reason"] == "weekend"
    assert body["from_cache"] is True
    assert len(fake_ecb.requests) == 1


def test_target_holiday_falls_back_to_previous_business_day(client):
    freeze_today("2026-04-07")  # Tuesday after Easter: catching up on the long weekend

    body = get_rate(client, "2026-04-03").json()  # Good Friday

    assert body["rate_date"] == "2026-04-02"
    assert body["fallback_reason"] == "target_holiday"
    assert "Good Friday" in body["note"]

    easter_monday = get_rate(client, "2026-04-06").json()
    assert easter_monday["rate_date"] == "2026-04-02"
    assert easter_monday["fallback_reason"] == "target_holiday"
    assert "Easter Monday" in easter_monday["note"]


def test_cache_stores_only_published_observations(client, session):
    freeze_today("2026-03-09")
    get_rate(client, SATURDAY)

    cached = session.exec(select(ExchangeRate).order_by(ExchangeRate.rate_date)).all()
    dates = {row.rate_date for row in cached}

    assert date(2026, 3, 6) in dates
    assert date(2026, 3, 7) not in dates
    assert all(target_closing_reason(day) is None for day in dates)
    assert all(row.currency == "USD" for row in cached)


def test_eur_is_rejected(client, fake_ecb):
    response = get_rate(client, FRIDAY, currency="EUR")

    assert response.status_code == 422
    assert "EUR" in response.json()["detail"]
    assert fake_ecb.requests == []


def test_unknown_currency_and_bad_date_are_validation_errors(client):
    assert get_rate(client, FRIDAY, currency="XYZ").status_code == 422
    assert get_rate(client, "06/03/2026").status_code == 422
    assert get_rate(client, FRIDAY, invoice_issued_on="yesterday").status_code == 422
    assert client.get("/api/exchange-rates").status_code == 422


# --- which day's rate (CIVA art. 49.º + art. 8.º n.º 1; CIRS art. 23.º) --------------------


def test_invoice_issued_before_payout_uses_the_invoice_date(client):
    freeze_today("2026-03-09")  # invoice Monday 2 March, payout Friday 6, entered Monday 9

    body = get_rate(client, FRIDAY, invoice_issued_on="2026-03-02").json()

    assert body["payout_date"] == FRIDAY
    assert body["invoice_issued_on"] == "2026-03-02"
    assert body["requested_date"] == "2026-03-02"
    assert body["rate_date"] == "2026-03-02"
    assert body["conversion_basis"] == "invoice_date"
    assert "CIVA art. 8.º n.º 1 al. a)" in body["conversion_note"]
    assert "CIVA art. 49.º n.º 1" in body["conversion_note"]
    assert FRIDAY in body["conversion_note"]  # IRS still looks at the payment day
    assert body["is_fallback"] is False


def test_invoice_first_returns_both_rates_and_flags_the_difference(client, fake_ecb):
    freeze_today("2026-03-09")

    body = get_rate(client, FRIDAY, invoice_issued_on="2026-03-02").json()

    assert body["rates_differ"] is True
    # Fatura-Recibo: the invoice day (CIVA art. 8.º n.º 1 al. a) + 49.º n.º 1)
    assert body["rate_date"] == "2026-03-02"
    assert Decimal(body["currency_per_eur"]) == Decimal("1.0814")
    # IRS income: the payment day (CIRS art. 23.º n.º 1 al. b))
    assert body["irs"]["requested_date"] == FRIDAY
    assert body["irs"]["rate_date"] == FRIDAY
    assert Decimal(body["irs"]["currency_per_eur"]) == Decimal("1.0817")
    assert body["irs"]["is_fallback"] is False
    assert body["irs"]["from_cache"] is False
    assert len(fake_ecb.requests) == 2  # two windows: up to 2 March, then up to 6 March

    again = get_rate(client, FRIDAY, invoice_issued_on="2026-03-02").json()
    assert again["from_cache"] is True and again["irs"]["from_cache"] is True
    assert len(fake_ecb.requests) == 2


def test_same_day_returns_the_same_rate_for_both(client, fake_ecb):
    freeze_today("2026-03-09")

    for invoice in (None, FRIDAY, "2026-03-09"):
        body = get_rate(client, FRIDAY, invoice_issued_on=invoice).json()
        assert body["rates_differ"] is False
        assert body["irs"]["rate_date"] == body["rate_date"] == FRIDAY
        assert body["irs"]["currency_per_eur"] == body["currency_per_eur"]
    assert len(fake_ecb.requests) == 1


def test_irs_rate_falls_back_when_the_payout_lands_on_a_weekend(client):
    freeze_today("2026-03-09")

    body = get_rate(client, SATURDAY, invoice_issued_on="2026-03-04").json()

    assert body["rate_date"] == "2026-03-04" and body["is_fallback"] is False
    assert body["irs"]["requested_date"] == SATURDAY
    assert body["irs"]["rate_date"] == FRIDAY
    assert body["irs"]["fallback_reason"] == "weekend"
    assert "Saturday 2026-03-07" in body["irs"]["note"]
    assert body["rates_differ"] is True


def test_rates_differ_is_about_days_not_values(client, fake_ecb):
    """Two different days can publish the same value; the user still has two dates to cite."""
    freeze_today("2026-03-09")
    fake_ecb.csv_body = "\n".join(
        line.replace(",1.0814", ",1.0817") if "2026-03-02" in line else line
        for line in fake_ecb.csv_body.splitlines()
    )

    body = get_rate(client, FRIDAY, invoice_issued_on="2026-03-02").json()

    assert body["currency_per_eur"] == body["irs"]["currency_per_eur"]
    assert body["rates_differ"] is True


def test_invoice_issued_on_or_after_payout_uses_the_payout_date(client):
    freeze_today("2026-03-09")  # Monday: issuing the Fatura-Recibo today for Friday's payout
    same_day = get_rate(client, FRIDAY, invoice_issued_on=FRIDAY).json()
    later = get_rate(client, FRIDAY, invoice_issued_on="2026-03-09").json()

    for body in (same_day, later):
        assert body["requested_date"] == FRIDAY
        assert body["conversion_basis"] == "payout_date"
    assert "before the invoice of 2026-03-09" in later["conversion_note"]


def test_fallback_applies_to_the_invoice_date_when_it_is_the_conversion_day(client):
    freeze_today("2026-03-13")  # invoice dated Saturday 7 March, payout arrives Friday 13

    body = get_rate(client, "2026-03-13", invoice_issued_on=SATURDAY).json()

    assert body["requested_date"] == SATURDAY
    assert body["conversion_basis"] == "invoice_date"
    assert body["rate_date"] == FRIDAY
    assert body["fallback_reason"] == "weekend"


@pytest.mark.parametrize(
    ("payout", "invoice", "expected_day", "expected_basis"),
    [
        (date(2026, 3, 6), None, date(2026, 3, 6), ConversionBasis.PAYOUT_DATE),
        (date(2026, 3, 6), date(2026, 3, 6), date(2026, 3, 6), ConversionBasis.PAYOUT_DATE),
        (date(2026, 3, 6), date(2026, 3, 9), date(2026, 3, 6), ConversionBasis.PAYOUT_DATE),
        (date(2026, 3, 6), date(2026, 3, 2), date(2026, 3, 2), ConversionBasis.INVOICE_DATE),
    ],
    ids=["no-invoice-yet", "same-day", "invoice-after-payout", "invoice-before-payout"],
)
def test_conversion_date_rule(payout, invoice, expected_day, expected_basis):
    result = conversion_date(payout, invoice)

    assert result.rate_date == expected_day
    assert result.basis == expected_basis
    assert "CIVA art. 8.º n.º 1" in result.explanation
    assert "CIRS art. 23.º n.º 1 al. b)" in result.explanation


def test_no_observations_in_window_is_404(client, fake_ecb):
    freeze_today("2025-06-09")
    response = get_rate(client, "2025-06-06")  # fixture has nothing in 2025

    assert response.status_code == 404
    assert "2025-05-23" in response.json()["detail"]
    assert "2025-06-06" in response.json()["detail"]
    assert len(fake_ecb.requests) == 1


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(503, text="Service unavailable"),
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(400, text="Syntax error"),
        httpx.Response(200, text="<html>maintenance</html>"),
        httpx.Response(200, text="TIME_PERIOD,OBS_VALUE\n2026-03-06,not-a-number\n"),
        httpx.ConnectError("Name or service not known"),
        httpx.ReadTimeout("timed out"),
        httpx.RemoteProtocolError("connection closed"),
    ],
    ids=["503", "500", "400", "html-body", "bad-value", "connect", "timeout", "protocol"],
)
def test_upstream_failures_map_to_502(client, fake_ecb, failure):
    freeze_today("2026-03-09")
    fake_ecb.respond_with(failure)

    response = get_rate(client, FRIDAY)

    assert response.status_code == 502
    assert response.json()["detail"].startswith("ECB Data Portal unavailable")


def test_upstream_failure_does_not_poison_the_cache(client, fake_ecb):
    freeze_today("2026-03-09")
    fake_ecb.respond_with(httpx.Response(503, text="Service unavailable"))
    assert get_rate(client, FRIDAY).status_code == 502

    fake_ecb.respond_with(httpx.Response(200, text=fake_ecb.csv_body))
    body = get_rate(client, FRIDAY).json()

    assert body["from_cache"] is False
    assert Decimal(body["currency_per_eur"]) == Decimal("1.0817")


# --- non-publication days: Easter runs, Christmas, New Year, 1 May (2026 and 2027) ----------

EASTER_2026 = "2026-04-02"  # Maundy Thursday: last ECB publication before Easter 2026
EASTER_2027 = "2027-03-25"  # Maundy Thursday 2027 (Easter Sunday is 2027-03-28)


@pytest.mark.parametrize(
    # "today" is when the user records the payout: sometimes the closure day itself,
    # sometimes the next business day when catching up after the holiday.
    ("today", "payout", "expected_rate_date", "reason", "mention"),
    [
        ("2026-04-03", "2026-04-03", EASTER_2026, "target_holiday", "Good Friday"),
        ("2026-04-04", "2026-04-04", EASTER_2026, "weekend", "Saturday 2026-04-04"),
        ("2026-04-07", "2026-04-05", EASTER_2026, "weekend", "Sunday 2026-04-05"),
        ("2026-04-06", "2026-04-06", EASTER_2026, "target_holiday", "Easter Monday"),
        ("2026-12-28", "2026-12-25", "2026-12-24", "target_holiday", "Christmas Day"),
        ("2026-12-26", "2026-12-26", "2026-12-24", "weekend", "Saturday 2026-12-26"),
        ("2026-12-28", "2026-12-27", "2026-12-24", "weekend", "Sunday 2026-12-27"),
        ("2027-01-01", "2027-01-01", "2026-12-31", "target_holiday", "New Year's Day"),
        ("2027-01-04", "2027-01-02", "2026-12-31", "weekend", "Saturday 2027-01-02"),
        ("2027-01-03", "2027-01-03", "2026-12-31", "weekend", "Sunday 2027-01-03"),
        ("2027-03-26", "2027-03-26", EASTER_2027, "target_holiday", "Good Friday"),
        ("2027-03-27", "2027-03-27", EASTER_2027, "weekend", "Saturday 2027-03-27"),
        ("2027-03-30", "2027-03-28", EASTER_2027, "weekend", "Sunday 2027-03-28"),
        ("2027-03-29", "2027-03-29", EASTER_2027, "target_holiday", "Easter Monday"),
        ("2027-05-03", "2027-05-01", "2027-04-30", "weekend", "Saturday 2027-05-01"),
        ("2027-12-25", "2027-12-25", "2027-12-24", "weekend", "Saturday 2027-12-25"),
        ("2027-12-27", "2027-12-26", "2027-12-24", "weekend", "Sunday 2027-12-26"),
    ],
    ids=[
        "2026-good-friday",
        "2026-holy-saturday",
        "2026-easter-sunday",
        "2026-easter-monday",
        "2026-christmas-friday",
        "2026-26-dec-saturday",
        "2026-27-dec-sunday",
        "2027-new-year-friday",
        "2027-jan-2-saturday",
        "2027-jan-3-sunday",
        "2027-good-friday",
        "2027-holy-saturday",
        "2027-easter-sunday",
        "2027-easter-monday",
        "2027-labour-day-on-saturday",
        "2027-christmas-saturday",
        "2027-26-dec-sunday",
    ],
)
def test_non_publication_days_fall_back_to_the_last_business_day(
    client, today, payout, expected_rate_date, reason, mention
):
    freeze_today(today)

    body = get_rate(client, payout).json()

    assert body["requested_date"] == payout
    assert body["rate_date"] == expected_rate_date
    assert body["is_fallback"] is True
    assert body["fallback_reason"] == reason
    assert mention in body["note"]
    assert expected_rate_date in body["note"]
    assert "CIRS art. 23.º n.º 3" in body["note"]


@pytest.mark.parametrize(
    "business_day",
    [
        "2026-04-02",
        "2026-04-07",
        "2026-12-24",
        "2026-12-28",
        "2026-12-31",
        "2027-03-25",
        "2027-03-30",
        "2027-04-30",
        "2027-05-03",
        "2027-12-24",
        "2027-12-27",
    ],
)
def test_business_days_around_the_closures_are_exact(client, business_day):
    freeze_today(business_day)  # entered the same evening, after the ~16:00 CET publication

    body = get_rate(client, business_day).json()

    assert body["rate_date"] == business_day
    assert body["is_fallback"] is False
    assert body["fallback_reason"] is None


def test_whole_easter_run_is_served_from_cache_after_one_fetch(client, fake_ecb):
    freeze_today("2027-03-30")  # Tuesday after Easter: entering the long weekend's payouts
    assert get_rate(client, EASTER_2027).json()["from_cache"] is False

    for closed_day in ("2027-03-26", "2027-03-27", "2027-03-28", "2027-03-29"):
        body = get_rate(client, closed_day).json()
        assert body["rate_date"] == EASTER_2027
        assert body["from_cache"] is True

    assert len(fake_ecb.requests) == 1


def test_new_year_fallback_is_cached_across_year_end(client, fake_ecb):
    freeze_today("2027-01-04")  # first Monday of the year
    get_rate(client, "2027-01-01")  # New Year's Day -> fetch window ending 2027-01-01

    body = get_rate(client, "2027-01-03").json()

    assert body["rate_date"] == "2026-12-31"
    assert body["from_cache"] is True
    assert len(fake_ecb.requests) == 1


# --- dates before the euro ---------------------------------------------------------------


@pytest.mark.parametrize("payout", ["1998-12-31", "1999-01-01", "1999-01-03", "1975-04-25"])
def test_dates_before_the_first_ecb_rates_are_422_without_calling_the_ecb(client, fake_ecb, payout):
    response = get_rate(client, payout)

    assert response.status_code == 422
    assert "1999-01-04" in response.json()["detail"]
    assert fake_ecb.requests == []


def test_pre_euro_date_is_422_even_when_the_ecb_is_down(client, fake_ecb):
    fake_ecb.respond_with(httpx.ConnectError("down"))

    assert get_rate(client, "1998-06-05").status_code == 422


def test_pre_euro_invoice_date_is_422_too(client, fake_ecb):
    response = get_rate(client, FRIDAY, invoice_issued_on="1998-12-31")

    assert response.status_code == 422
    assert fake_ecb.requests == []


def test_first_ecb_business_day_is_asked_from_the_ecb(client, fake_ecb):
    freeze_today("1999-01-05")
    response = get_rate(client, "1999-01-04")  # fake ECB has no 1999 data -> 404, never 502

    assert response.status_code == 404
    assert fake_ecb.requests[0].url.params["endPeriod"] == "1999-01-04"


def test_service_raises_unsupported_date(session, fake_ecb):
    with pytest.raises(UnsupportedRateDate):
        lookup_exchange_rate(session, fake_ecb.client(), Currency.USD, date(1998, 12, 31))


# --- dates in the future -----------------------------------------------------------------


@pytest.mark.parametrize("payout", ["2026-03-10", "2026-03-20", "2031-01-02"])
def test_future_dates_fall_back_to_the_latest_published_rate(client, fake_ecb, payout):
    freeze_today("2026-03-09")
    without_days(fake_ecb, "2026-03-09")  # Monday's rate not out yet either

    body = get_rate(client, payout).json()

    assert body["requested_date"] == payout
    assert body["rate_date"] == FRIDAY
    assert body["fallback_reason"] == "not_yet_published"
    assert "not published a reference rate for " + payout in body["note"]
    assert "check again once it is published" in body["note"]
    assert fake_ecb.requests[0].url.params["endPeriod"] == "2026-03-09"  # never beyond today
    assert fake_ecb.requests[0].url.params["startPeriod"] == "2026-02-23"


@pytest.mark.parametrize(
    ("payout", "reason"),
    [("2026-03-14", "weekend"), ("2026-04-03", "target_holiday"), ("2031-01-01", "target_holiday")],
    ids=["next-saturday", "good-friday-next-month", "new-year-2031"],
)
def test_future_closing_days_are_explained_by_the_calendar(client, payout, reason):
    freeze_today("2026-03-09")

    body = get_rate(client, payout).json()

    assert body["rate_date"] == "2026-03-09"  # still the latest published rate
    assert body["fallback_reason"] == reason


def test_future_lookups_are_not_cached_as_rates(client, session, fake_ecb):
    freeze_today("2026-03-09")
    get_rate(client, "2026-03-20")

    cached = {row.rate_date for row in session.exec(select(ExchangeRate)).all()}

    assert date(2026, 3, 20) not in cached
    assert max(cached) == date(2026, 3, 9)


# --- today, before and after the ~16:00 CET publication -----------------------------------


def test_today_on_a_weekend_is_a_weekend_not_a_pending_publication(client):
    freeze_today("2026-03-07")  # Saturday

    body = get_rate(client, "2026-03-07").json()

    assert body["fallback_reason"] == "weekend"
    assert body["rate_date"] == FRIDAY


def test_yesterday_missing_is_reported_as_no_rate_published(client, fake_ecb):
    freeze_today("2026-03-10")
    without_days(fake_ecb, "2026-03-09")  # an unexpected closure on a past weekday

    body = get_rate(client, "2026-03-09").json()

    assert body["rate_date"] == FRIDAY
    assert body["fallback_reason"] == "no_rate_published"


# --- cache behaviour -------------------------------------------------------------------------


def cached_days(session) -> set[date]:
    return {row.rate_date for row in session.exec(select(ExchangeRate)).all()}


@pytest.mark.parametrize(
    ("today", "closed_day", "expected_rate_date"),
    [
        ("2026-03-09", "2026-03-07", FRIDAY),
        ("2026-03-09", "2026-03-08", FRIDAY),
        ("2026-04-07", "2026-04-03", "2026-04-02"),
        ("2026-04-07", "2026-04-06", "2026-04-02"),
        ("2026-12-28", "2026-12-25", "2026-12-24"),
    ],
    ids=["saturday", "sunday", "good-friday", "easter-monday", "christmas"],
)
def test_repeated_lookups_of_a_closure_day_never_touch_the_network_again(
    client, fake_ecb, today, closed_day, expected_rate_date
):
    freeze_today(today)
    first = get_rate(client, closed_day).json()
    assert first["rate_date"] == expected_rate_date
    assert first["from_cache"] is False
    assert len(fake_ecb.requests) == 1

    fake_ecb.respond_with(httpx.ConnectError("network is gone"))  # any further call would 502

    for _ in range(3):
        again = get_rate(client, closed_day)
        assert again.status_code == 200
        assert again.json()["rate_date"] == expected_rate_date
        assert again.json()["from_cache"] is True
    assert len(fake_ecb.requests) == 1


def test_other_closure_days_of_the_same_run_are_answered_from_the_cache(client, fake_ecb):
    freeze_today("2026-04-07")
    get_rate(client, "2026-04-03")  # Good Friday: one fetch, caches Thursday 2026-04-02
    fake_ecb.respond_with(httpx.ConnectError("network is gone"))

    for day in ("2026-04-04", "2026-04-05", "2026-04-06"):
        body = get_rate(client, day).json()
        assert body["rate_date"] == "2026-04-02"
        assert body["from_cache"] is True
    assert len(fake_ecb.requests) == 1


def test_closure_days_are_never_written_to_the_cache(client, session, fake_ecb):
    freeze_today("2026-04-07")
    for day in ("2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06"):
        get_rate(client, day)

    assert date(2026, 4, 2) in cached_days(session)
    assert not {date(2026, 4, d) for d in (3, 4, 5, 6)} & cached_days(session)


def test_no_data_for_today_is_not_cached_and_is_refetched_after_publication(
    client, session, fake_ecb
):
    today = "2026-03-09"  # Monday
    freeze_today(today)
    published = fake_ecb.csv_body
    without_days(fake_ecb, today)

    # 09:00, 12:00, 15:59 CET: nothing published yet -> Friday's rate, asked from the ECB
    # every time, because "no rate for today" must never be remembered.
    for lookup in range(1, 4):
        body = get_rate(client, today).json()
        assert body["rate_date"] == FRIDAY
        assert body["fallback_reason"] == "not_yet_published"
        assert "16:00 CET" in body["note"]
        assert body["from_cache"] is False
        assert len(fake_ecb.requests) == lookup
    assert date(2026, 3, 6) in cached_days(session)
    assert date(2026, 3, 9) not in cached_days(session)

    fake_ecb.csv_body = published  # 16:05 CET: the ECB has published Monday's rate

    after = get_rate(client, today).json()
    assert after["rate_date"] == today
    assert after["is_fallback"] is False
    assert after["from_cache"] is False
    assert len(fake_ecb.requests) == 4
    assert date(2026, 3, 9) in cached_days(session)

    assert get_rate(client, today).json()["from_cache"] is True  # and only now it sticks
    assert len(fake_ecb.requests) == 4


def test_no_data_for_today_does_not_block_the_previous_day_cache(client, fake_ecb):
    freeze_today("2026-03-10")  # Tuesday morning, Monday's and Tuesday's rates both known
    without_days(fake_ecb, "2026-03-10")
    get_rate(client, "2026-03-10")  # fetches the window, caches up to Monday
    fake_ecb.respond_with(httpx.ConnectError("network is gone"))

    monday = get_rate(client, "2026-03-09").json()

    assert monday["rate_date"] == "2026-03-09"
    assert monday["from_cache"] is True


def test_losing_an_insert_race_is_handled_and_nothing_is_lost(file_engine, fake_ecb):
    """Deterministic replay of two requests storing the same window: just before the first
    session flushes its inserts, a second connection inserts (and commits) the same rows."""
    from sqlalchemy import event

    from app.exchange_rates import _store

    observations = fake_ecb.client().fetch_daily_rates("USD", date(2026, 3, 2), date(2026, 3, 6))
    assert len(observations) == 5
    with Session(file_engine) as loser, Session(file_engine) as winner:
        fired = False

        def winner_commits_first(session, flush_context, instances):
            nonlocal fired
            if fired:  # the retry flushes again; the race happens only once
                return
            fired = True
            _store(winner, "USD", observations[:3])  # winner got a shorter window
            assert len(cached_days(winner)) == 3

        event.listen(loser, "before_flush", winner_commits_first)

        _store(loser, "USD", observations)  # IntegrityError on the first 3 -> rollback -> retry

        assert fired
        assert cached_days(loser) == {o.rate_date for o in observations}
        assert len(loser.exec(select(ExchangeRate)).all()) == 5  # one row per day, no duplicates


def test_losing_the_retry_too_gives_up_with_a_warning(file_engine, fake_ecb, caplog):
    """Another writer wins both rounds: the loser rolls back twice and logs, but does not raise."""
    from sqlalchemy import event

    from app.exchange_rates import _store

    observations = fake_ecb.client().fetch_daily_rates("USD", date(2026, 3, 2), date(2026, 3, 6))
    with Session(file_engine) as loser, Session(file_engine) as winner:
        rounds = iter([observations[:2], observations[2:]])

        def winner_always_first(session, flush_context, instances):
            batch = next(rounds, None)
            if batch:
                _store(winner, "USD", batch)

        event.listen(loser, "before_flush", winner_always_first)

        with caplog.at_level("WARNING", logger="app.exchange_rates"):
            _store(loser, "USD", observations)

        assert "Could not cache ECB rates for USD" in caplog.text
        assert len(loser.exec(select(ExchangeRate)).all()) == 5  # the winner's rows, intact


def test_ecb_client_dependency_closes_the_client_after_the_request():
    settings = Settings(_env_file=None, ecb_api_base_url="https://ecb.test/service")
    dependency = get_ecb_client(settings)

    client = next(dependency)
    assert client._client.is_closed is False
    assert str(client._client.base_url) == "https://ecb.test/service/"

    with pytest.raises(StopIteration):
        next(dependency)  # FastAPI runs the teardown after the response
    assert client._client.is_closed is True


def test_concurrent_requests_for_the_same_uncached_day_both_succeed(file_client, fake_ecb):
    import threading

    freeze_today("2026-03-09")
    both_fetching = threading.Barrier(2, timeout=10)

    def slow_ecb(request: httpx.Request) -> httpx.Response:
        both_fetching.wait()  # neither request may store before the other has fetched
        return fake_ecb.fixture_response(request)

    fake_ecb.respond_with(slow_ecb)

    results: dict[int, httpx.Response] = {}

    def lookup(index: int) -> None:
        results[index] = get_rate(file_client, FRIDAY)

    threads = [threading.Thread(target=lookup, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(fake_ecb.requests) == 2  # both missed the cache and went to the ECB
    assert [results[i].status_code for i in range(2)] == [200, 200]
    bodies = [results[i].json() for i in range(2)]
    assert bodies[0]["rate_date"] == bodies[1]["rate_date"] == FRIDAY
    assert bodies[0]["currency_per_eur"] == bodies[1]["currency_per_eur"]

    fake_ecb.respond_with(httpx.ConnectError("network is gone"))
    assert get_rate(file_client, FRIDAY).json()["from_cache"] is True  # exactly one row stuck
    assert get_rate(file_client, SATURDAY).json()["from_cache"] is True


# --- service --------------------------------------------------------------------------------


def test_today_before_publication_falls_back_with_not_yet_published(session, fake_ecb):
    today = date(2026, 3, 9)  # Monday; fixture has no rate for it yet
    fake_ecb.csv_body = "\n".join(
        line for line in fake_ecb.csv_body.splitlines() if "2026-03-09" not in line
    )

    result = lookup_exchange_rate(session, fake_ecb.client(), Currency.USD, today, today=today)

    assert result.rate_date == date(2026, 3, 6)
    assert result.fallback_reason == "not_yet_published"
    assert "16:00 CET" in result.note


def test_future_date_does_not_query_beyond_today(session, fake_ecb):
    today = date(2026, 3, 6)

    result = lookup_exchange_rate(
        session, fake_ecb.client(), Currency.USD, date(2026, 3, 20), today=today
    )

    assert result.rate_date == today
    assert result.fallback_reason == "not_yet_published"
    assert fake_ecb.requests[0].url.params["endPeriod"] == "2026-03-06"


def test_unexpected_closure_on_a_weekday_is_explained(session, fake_ecb):
    fake_ecb.csv_body = "\n".join(
        line for line in fake_ecb.csv_body.splitlines() if "2026-03-04" not in line
    )

    result = lookup_exchange_rate(
        session, fake_ecb.client(), Currency.USD, date(2026, 3, 4), today=date(2026, 3, 9)
    )

    assert result.rate_date == date(2026, 3, 3)
    assert result.fallback_reason == "no_rate_published"


def test_service_raises_not_found_when_window_is_empty(session, fake_ecb):
    fake_ecb.respond_with(httpx.Response(404, text="No results found."))

    with pytest.raises(ExchangeRateNotFound):
        lookup_exchange_rate(session, fake_ecb.client(), Currency.USD, date(2026, 3, 6))


def test_service_rejects_eur(session, fake_ecb):
    with pytest.raises(ValueError):
        lookup_exchange_rate(session, fake_ecb.client(), Currency.EUR, date(2026, 3, 6))


# --- ECB client & calendar ------------------------------------------------------------------


def test_parse_csv_observations_uses_named_columns_and_skips_gaps(ecb_usd_csv):
    observations = parse_csv_observations(ecb_usd_csv)

    assert observations[0].rate_date == date(2026, 2, 16)
    assert observations[-1].rate_date == date(2027, 12, 31)
    assert all(target_closing_reason(o.rate_date) is None for o in observations)
    assert all(isinstance(o.currency_per_eur, Decimal) for o in observations)

    with_gap = "TIME_PERIOD,OBS_VALUE,OBS_STATUS\n2026-03-05,1.08,A\n2026-03-06,,-\n"
    assert [o.rate_date for o in parse_csv_observations(with_gap)] == [date(2026, 3, 5)]
    assert parse_csv_observations("") == []


def test_parses_the_live_dataonly_layout_with_crlf(ecb_live_csv):
    assert b"\r\n" in ecb_live_csv
    observations = parse_csv_observations(ecb_live_csv.decode())

    assert [(o.rate_date.isoformat(), o.currency_per_eur) for o in observations] == [
        ("2026-03-02", Decimal("1.1698")),
        ("2026-03-03", Decimal("1.1606")),
    ]


def test_endpoint_with_the_live_payload(client, fake_ecb, ecb_live_csv):
    fake_ecb.respond_with(
        httpx.Response(
            200,
            content=ecb_live_csv,
            headers={
                "content-type": "text/csv",
                "content-disposition": "attachment;filename=data.csv",
            },
        )
    )

    freeze_today("2026-03-04")
    body = get_rate(client, "2026-03-03").json()

    assert body["rate_date"] == "2026-03-03"
    assert Decimal(body["currency_per_eur"]) == Decimal("1.1606")
    assert body["is_fallback"] is False


def test_parse_csv_observations_rejects_unknown_layout():
    with pytest.raises(EcbUnavailable):
        parse_csv_observations("DATE,RATE\n2026-03-06,1.08\n")


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5))],
)
def test_easter_sunday(year, expected):
    assert easter_sunday(year) == expected


@pytest.mark.parametrize(
    ("day", "reason"),
    [
        (date(2026, 3, 6), None),
        (date(2026, 3, 7), "Saturday"),
        (date(2026, 3, 8), "Sunday"),
        (date(2026, 1, 1), "New Year's Day"),
        (date(2026, 4, 3), "Good Friday"),
        (date(2026, 4, 6), "Easter Monday"),
        (date(2026, 5, 1), "Labour Day"),
        (date(2026, 12, 25), "Christmas Day"),
        (date(2026, 12, 28), None),
        (date(2025, 12, 26), "26 December"),
    ],
)
def test_target_closing_reason(day, reason):
    assert target_closing_reason(day) == reason


def test_previous_target_business_day_skips_holiday_runs():
    assert previous_target_business_day(date(2026, 4, 7)) == date(2026, 4, 2)
    assert previous_target_business_day(date(2026, 3, 9)) == date(2026, 3, 6)
    assert previous_target_business_day(date(2026, 12, 28)) == date(2026, 12, 24)
