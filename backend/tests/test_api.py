from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import select

from app.main import create_app
from app.models import PayoutRateProvenance

USD_PAYOUT = {
    "payout_date": "2026-03-06",
    "currency": "USD",
    "original_amount": "1085.00",
    "currency_per_eur": "1.085",
}


def test_create_usd_payout_converts_to_eur(client):
    response = client.post("/api/payouts", json=USD_PAYOUT)

    assert response.status_code == 201
    assert Decimal(response.json()["eur_amount"]) == Decimal("1000.00")


def test_payout_stores_document_and_irs_pairs(client):
    payload = {
        **USD_PAYOUT,
        "invoice_issued_on": "2026-03-02",
        "currency_per_eur": "1.0850",  # invoice day (CIVA art. 49.º) -> Fatura-Recibo amount
        "rate_date": "2026-03-02",
        "irs_currency_per_eur": "1.1698",  # payout day (CIRS art. 23.º) -> IRS income
        "irs_rate_date": "2026-03-06",
    }

    body = client.post("/api/payouts", json=payload).json()

    assert Decimal(body["eur_amount"]) == Decimal("1000.00")
    assert body["rate_date"] == "2026-03-02"
    assert Decimal(body["irs_currency_per_eur"]) == Decimal("1.1698")
    assert Decimal(body["irs_eur_amount"]) == Decimal("927.51")
    assert body["irs_rate_date"] == "2026-03-06"


ECB_PROVENANCE = {
    "source": "ecb",
    "requested_date": "2026-03-07",
    "ecb_rate_date": "2026-03-06",
    "ecb_currency_per_eur": "1.0817",
    "is_fallback": True,
    "fallback_reason": "weekend",
    "fetched_at": "2026-03-09T10:00:00Z",
}
MANUAL_WITH_EVIDENCE = {
    **ECB_PROVENANCE,
    "source": "manual",
    "requested_date": "2026-03-02",
    "ecb_rate_date": "2026-03-02",
    "ecb_currency_per_eur": "1.1698",
    "is_fallback": False,
    "fallback_reason": None,
}


def test_payout_persists_rate_provenance_for_both_pairs(client, session):
    payload = {
        **USD_PAYOUT,
        "payout_date": "2026-03-07",
        "invoice_issued_on": "2026-03-02",
        "currency_per_eur": "1.1700",  # user rounded the ECB 1.1698 -> manual, evidence kept
        "irs_currency_per_eur": "1.0817",  # ECB value used as-is (Friday, weekend fallback)
        "rate_provenance": MANUAL_WITH_EVIDENCE,
        "irs_rate_provenance": ECB_PROVENANCE,
    }

    created = client.post("/api/payouts", json=payload)

    assert created.status_code == 201
    body = created.json()
    assert body["rate_provenance"] == {**MANUAL_WITH_EVIDENCE, "purpose": "document"} | {
        "ecb_currency_per_eur": "1.169800"
    }
    assert body["irs_rate_provenance"] == {**ECB_PROVENANCE, "purpose": "irs"} | {
        "ecb_currency_per_eur": "1.081700"
    }
    listed = client.get("/api/payouts", params={"year": 2026}).json()[0]
    assert listed["rate_provenance"]["source"] == "manual"
    assert listed["irs_rate_provenance"]["is_fallback"] is True
    assert len(session.exec(select(PayoutRateProvenance)).all()) == 2


def test_payout_without_provenance_reads_as_null(client):
    body = client.post("/api/payouts", json=USD_PAYOUT).json()

    assert body["rate_provenance"] is None
    assert body["irs_rate_provenance"] is None


def test_update_replaces_provenance_and_delete_removes_it(client, session):
    payout_id = client.post(
        "/api/payouts",
        json={
            **USD_PAYOUT,
            "rate_provenance": ECB_PROVENANCE,
            "irs_rate_provenance": ECB_PROVENANCE,
        },
    ).json()["id"]
    assert len(session.exec(select(PayoutRateProvenance)).all()) == 2

    updated = client.put(
        f"/api/payouts/{payout_id}",
        json={**USD_PAYOUT, "currency_per_eur": "1.09", "rate_provenance": MANUAL_WITH_EVIDENCE},
    ).json()

    assert updated["rate_provenance"]["source"] == "manual"
    assert updated["irs_rate_provenance"] is None  # not sent again -> gone
    session.expire_all()
    assert len(session.exec(select(PayoutRateProvenance)).all()) == 1

    assert client.delete(f"/api/payouts/{payout_id}").status_code == 204
    session.expire_all()
    assert session.exec(select(PayoutRateProvenance)).all() == []


def test_provenance_is_validated(client):
    bad_source = {**USD_PAYOUT, "rate_provenance": {**ECB_PROVENANCE, "source": "guess"}}
    bad_rate = {**USD_PAYOUT, "rate_provenance": {**ECB_PROVENANCE, "ecb_currency_per_eur": "0"}}

    assert client.post("/api/payouts", json=bad_source).status_code == 422
    assert client.post("/api/payouts", json=bad_rate).status_code == 422


def test_irs_rate_defaults_to_the_document_rate(client):
    body = client.post("/api/payouts", json=USD_PAYOUT).json()

    assert Decimal(body["irs_currency_per_eur"]) == Decimal("1.085")
    assert body["irs_eur_amount"] == body["eur_amount"]
    assert body["rate_date"] is None and body["irs_rate_date"] is None


def test_update_recomputes_both_amounts(client):
    payout_id = client.post("/api/payouts", json=USD_PAYOUT).json()["id"]

    updated = client.put(
        f"/api/payouts/{payout_id}",
        json={**USD_PAYOUT, "currency_per_eur": "1.0850", "irs_currency_per_eur": "1.0000"},
    ).json()

    assert Decimal(updated["eur_amount"]) == Decimal("1000.00")
    assert Decimal(updated["irs_eur_amount"]) == Decimal("1085.00")


def test_eur_payout_rejects_non_unit_rate(client):
    payload = {**USD_PAYOUT, "currency": "EUR"}

    assert client.post("/api/payouts", json=payload).status_code == 422
    assert (
        client.post(
            "/api/payouts",
            json={
                **USD_PAYOUT,
                "currency": "EUR",
                "currency_per_eur": "1",
                "irs_currency_per_eur": "1.1",
            },
        ).status_code
        == 422
    )


def test_negative_amount_is_rejected(client):
    payload = {**USD_PAYOUT, "original_amount": "-5"}

    assert client.post("/api/payouts", json=payload).status_code == 422


def test_update_and_delete_payout(client):
    payout_id = client.post("/api/payouts", json=USD_PAYOUT).json()["id"]

    updated = client.put(
        f"/api/payouts/{payout_id}", json={**USD_PAYOUT, "original_amount": "2170"}
    )
    assert Decimal(updated.json()["eur_amount"]) == Decimal("2000.00")

    assert client.delete(f"/api/payouts/{payout_id}").status_code == 204
    assert client.get("/api/payouts").json() == []


def test_invoice_fields_contain_portal_strings(client):
    payout_id = client.post("/api/payouts", json=USD_PAYOUT).json()["id"]

    fields = client.get(f"/api/payouts/{payout_id}/invoice-fields").json()
    by_label = {field["portal_label"]: field["value"] for field in fields}

    assert (
        by_label["Retenção na fonte de IRS"] == "Sem retenção - Não residente sem estabelecimento"
    )
    assert by_label["Valor base (EUR)"] == "1.000,00"
    assert by_label["Data da prestação do serviço"] == "06/03/2026"
    assert "USD 1085.00" in by_label["Descrição"]
    assert "BCE" not in by_label["Descrição"]  # rate day unknown: entered manually


def test_invoice_fields_use_the_document_amount_and_cite_the_rate_day(client):
    payout_id = client.post(
        "/api/payouts",
        json={
            **USD_PAYOUT,
            "invoice_issued_on": "2026-03-02",
            "rate_date": "2026-03-02",
            "irs_currency_per_eur": "1.1698",
            "irs_rate_date": "2026-03-06",
        },
    ).json()["id"]

    fields = client.get(f"/api/payouts/{payout_id}/invoice-fields").json()
    by_label = {field["portal_label"]: field["value"] for field in fields}

    assert by_label["Valor base (EUR)"] == "1.000,00"  # document pair, not the IRS 927,51
    assert by_label["Importância recebida (EUR)"] == "1.000,00"
    assert (
        "taxa de câmbio 1,0850 USD/EUR (taxa de referência do BCE de 02/03/2026)"
        in (by_label["Descrição"])
    )


def test_dashboard_aggregates_payouts(client):
    client.post("/api/payouts", json=USD_PAYOUT)
    client.post("/api/payouts", json={**USD_PAYOUT, "payout_date": "2026-03-13"})

    overview = client.get("/api/dashboard", params={"year": 2026}).json()

    assert Decimal(overview["gross"]) == Decimal("2000.00")
    assert Decimal(overview["monthly"][2]["gross"]) == Decimal("2000.00")
    assert len(overview["weekly"]) == 2
    assert Decimal(overview["savings_target"]) == Decimal("500.00")


def test_dashboard_uses_the_irs_amount_when_the_rates_differ(client):
    client.post(
        "/api/payouts",
        json={**USD_PAYOUT, "invoice_issued_on": "2026-03-02", "irs_currency_per_eur": "1.1698"},
    )
    client.post("/api/payouts", json=USD_PAYOUT)  # same rate for both: 1000.00

    overview = client.get("/api/dashboard", params={"year": 2026}).json()

    assert Decimal(overview["gross"]) == Decimal("927.51") + Decimal("1000.00")
    assert Decimal(overview["monthly"][2]["gross"]) == Decimal("1927.51")


def test_unsupported_year_returns_422(client):
    response = client.get("/api/dashboard", params={"year": 2019})

    assert response.status_code == 422
    assert "2019" in response.json()["detail"]


def test_ics_download(client):
    response = client.get("/api/calendar/deadlines.ics", params={"year": 2026})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in response.text


def test_sync_without_caldav_configuration_returns_409(client):
    assert client.post("/api/calendar/sync", params={"year": 2026}).status_code == 409


def test_frontend_is_served_without_shadowing_the_api(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")
    client = TestClient(create_app(str(tmp_path)))

    assert client.get("/").text == "<html></html>"
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/..%2fpyproject.toml").status_code == 404


def test_missing_payout_is_404_everywhere(client):
    assert client.get("/api/payouts/999/invoice-fields").status_code == 404
    assert client.put("/api/payouts/999", json=USD_PAYOUT).status_code == 404
    assert client.delete("/api/payouts/999").status_code == 404


def test_fiscal_parameters_and_years(client):
    years = client.get("/api/fiscal-parameters/years").json()
    assert years == [2026]

    parameters = client.get("/api/fiscal-parameters", params={"year": 2026}).json()
    assert parameters["year"] == 2026
    assert Decimal(parameters["ias"]) == Decimal("537.13")
    assert client.get("/api/fiscal-parameters", params={"year": 2019}).status_code == 422


def test_irs_estimate_endpoint_defaults_employment_to_settings(client, settings):
    with_default = client.get(
        "/api/estimates/irs", params={"year": 2026, "freelance_gross": "10000"}
    ).json()
    explicit = client.get(
        "/api/estimates/irs",
        params={"year": 2026, "freelance_gross": "10000", "employment_gross": "42000"},
    ).json()

    assert Decimal(with_default["employment_gross"]) == (
        settings.employment_monthly_gross_salary * settings.employment_payments_per_year
    )
    assert Decimal(explicit["employment_gross"]) == Decimal("42000")
    assert Decimal(with_default["freelance_taxable_income"]) == Decimal("7500.00")
    assert Decimal(explicit["freelance_tax_impact"]) > 0


def test_social_security_estimate_endpoint(client):
    employed = client.get(
        "/api/estimates/social-security",
        params={"year": 2026, "quarter": 2, "services_income": "3000"},
    ).json()
    alone = client.get(
        "/api/estimates/social-security",
        params={
            "year": 2026,
            "quarter": 2,
            "services_income": "3000",
            "accumulates_with_employment": "false",
        },
    ).json()

    assert employed["quarter"] == 2
    assert Decimal(employed["quarterly_contribution"]) == Decimal("0")  # below 4 x IAS
    assert Decimal(alone["quarterly_contribution"]) > 0
    assert (
        client.get(
            "/api/estimates/social-security",
            params={"year": 2026, "quarter": 5, "services_income": "1"},
        ).status_code
        == 422
    )


def test_calendar_deadlines_and_status(client, settings):
    deadlines = client.get("/api/calendar/deadlines", params={"year": 2026}).json()
    assert len(deadlines) > 0
    assert all({"key", "title", "due", "guide_markdown", "links"} <= set(d) for d in deadlines)

    assert client.get("/api/calendar/status").json() == {
        "configured": False,
        "calendar_url": settings.caldav_calendar_url,
    }
