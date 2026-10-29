from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app

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


def test_eur_payout_rejects_non_unit_rate(client):
    payload = {**USD_PAYOUT, "currency": "EUR"}

    assert client.post("/api/payouts", json=payload).status_code == 422


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


def test_dashboard_aggregates_payouts(client):
    client.post("/api/payouts", json=USD_PAYOUT)
    client.post("/api/payouts", json={**USD_PAYOUT, "payout_date": "2026-03-13"})

    overview = client.get("/api/dashboard", params={"year": 2026}).json()

    assert Decimal(overview["gross"]) == Decimal("2000.00")
    assert Decimal(overview["monthly"][2]["gross"]) == Decimal("2000.00")
    assert len(overview["weekly"]) == 2
    assert Decimal(overview["savings_target"]) == Decimal("500.00")


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
