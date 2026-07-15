import uuid


async def test_import_csv_categorizes_and_skips_bad_rows(db_session, client, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    owner_id = uuid.UUID(me.json()["id"])

    from app.services.import_service import import_csv

    csv_content = (
        b"Txn Date,Withdrawal Amt.,Deposit Amt.,Narration\n"
        b"01/01/2026,250,,SWIGGY BANGALORE\n"
        b"02/01/2026,,50000,SALARY CREDIT\n"
        b"03/01/2026,not-a-number,,BAD ROW\n"
    )

    summary = await import_csv(db_session, owner_id, csv_content)
    assert summary.rows_total == 3
    assert summary.rows_imported == 1
    assert summary.rows_skipped == 2


async def test_import_csv_via_endpoint_categorizes_known_merchant(client, auth_headers):
    csv_content = (
        b"Date,Amount,Merchant\n"
        b"05/01/2026,499,Netflix\n"
        b"06/01/2026,150,Uber\n"
    )

    response = await client.post(
        "/api/v1/import/csv",
        headers=auth_headers,
        files={"file": ("statement.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rows_imported"] == 2
    assert body["rows_skipped"] == 0

    expenses = await client.get("/api/v1/expenses?page_size=50", headers=auth_headers)
    merchants = {item["merchant"] for item in expenses.json()["items"]}
    assert "Netflix" in merchants
    assert "Uber" in merchants


async def test_import_csv_rejects_file_without_detectable_columns(client, auth_headers):
    csv_content = b"foo,bar\n1,2\n"
    response = await client.post(
        "/api/v1/import/csv",
        headers=auth_headers,
        files={"file": ("bad.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 400
