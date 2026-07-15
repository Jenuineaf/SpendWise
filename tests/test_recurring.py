from datetime import date, timedelta


async def _category_id(client, headers, name):
    response = await client.get("/api/v1/categories", headers=headers)
    for category in response.json():
        if category["name"] == name:
            return category["id"]
    raise AssertionError(f"default category {name} missing")


async def test_materialize_due_expenses_catches_up_overdue_daily_rule(
    client, auth_headers, db_session
):
    category_id = await _category_id(client, auth_headers, "Bills & Utilities")
    overdue_start = date.today() - timedelta(days=3)

    create = await client.post(
        "/api/v1/recurring",
        headers=auth_headers,
        json={
            "category_id": category_id,
            "amount": "20.00",
            "cadence": "daily",
            "next_run": str(overdue_start),
        },
    )
    assert create.status_code == 201

    from app.services.recurring_service import materialize_due_expenses

    created = await materialize_due_expenses(db_session)
    assert created >= 4  # 3 overdue days + today

    rules = await client.get("/api/v1/recurring", headers=auth_headers)
    matched = next(r for r in rules.json() if r["id"] == create.json()["id"])
    assert matched["next_run"] > str(date.today())


async def test_recurring_rule_can_be_deactivated(client, auth_headers):
    category_id = await _category_id(client, auth_headers, "Rent")
    create = await client.post(
        "/api/v1/recurring",
        headers=auth_headers,
        json={
            "category_id": category_id,
            "amount": "15000.00",
            "cadence": "monthly",
            "next_run": str(date.today()),
        },
    )
    rule_id = create.json()["id"]

    response = await client.patch(
        f"/api/v1/recurring/{rule_id}", headers=auth_headers, json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
