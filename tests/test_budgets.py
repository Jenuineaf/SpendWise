from datetime import date


async def _category_id(client, headers, name):
    response = await client.get("/api/v1/categories", headers=headers)
    for category in response.json():
        if category["name"] == name:
            return category["id"]
    raise AssertionError(f"default category {name} missing")


async def test_budget_spent_vs_amount_math(client, auth_headers):
    category_id = await _category_id(client, auth_headers, "Groceries")
    today = date.today()

    budget = await client.post(
        "/api/v1/budgets",
        headers=auth_headers,
        json={
            "category_id": category_id,
            "year": today.year,
            "month": today.month,
            "amount": "1000.00",
        },
    )
    assert budget.status_code == 201
    assert budget.json()["spent"] == "0"

    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "850.00", "category_id": category_id, "date": str(today)},
    )

    listing = await client.get(
        f"/api/v1/budgets?year={today.year}&month={today.month}", headers=auth_headers
    )
    matched = next(b for b in listing.json() if b["category_id"] == category_id)
    assert matched["spent"] == "850.00"
    assert matched["remaining"] == "150.00"
    assert matched["percent_used"] == 85.0


async def test_duplicate_budget_for_same_month_rejected(client, auth_headers):
    category_id = await _category_id(client, auth_headers, "Shopping")
    today = date.today()
    payload = {
        "category_id": category_id,
        "year": today.year,
        "month": today.month,
        "amount": "500.00",
    }

    first = await client.post("/api/v1/budgets", headers=auth_headers, json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/budgets", headers=auth_headers, json=payload)
    assert second.status_code == 409


async def test_budget_alert_recorded_when_threshold_crossed(client, auth_headers):
    category_id = await _category_id(client, auth_headers, "Entertainment")
    today = date.today()
    await client.post(
        "/api/v1/budgets",
        headers=auth_headers,
        json={
            "category_id": category_id,
            "year": today.year,
            "month": today.month,
            "amount": "100.00",
        },
    )
    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "90.00", "category_id": category_id, "date": str(today)},
    )

    alerts = await client.get("/api/v1/alerts", headers=auth_headers)
    thresholds = {a["threshold"] for a in alerts.json()}
    assert 80 in thresholds
    assert 100 not in thresholds


async def test_budget_alert_does_not_repeat_for_same_threshold(client, auth_headers):
    category_id = await _category_id(client, auth_headers, "Health")
    today = date.today()
    await client.post(
        "/api/v1/budgets",
        headers=auth_headers,
        json={
            "category_id": category_id,
            "year": today.year,
            "month": today.month,
            "amount": "100.00",
        },
    )
    for _ in range(2):
        await client.post(
            "/api/v1/expenses",
            headers=auth_headers,
            json={"amount": "90.00", "category_id": category_id, "date": str(today)},
        )

    alerts = await client.get("/api/v1/alerts", headers=auth_headers)
    eighty_count = sum(1 for a in alerts.json() if a["threshold"] == 80)
    assert eighty_count == 1
