from datetime import date


async def _category_id(client, headers, name):
    response = await client.get("/api/v1/categories", headers=headers)
    for category in response.json():
        if category["name"] == name:
            return category["id"]
    raise AssertionError(f"default category {name} missing")


async def test_category_breakdown_percentages_sum_to_100(client, auth_headers):
    today = date.today()
    food_id = await _category_id(client, auth_headers, "Food & Dining")
    transport_id = await _category_id(client, auth_headers, "Transport")

    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "300.00", "category_id": food_id, "date": str(today)},
    )
    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "100.00", "category_id": transport_id, "date": str(today)},
    )

    response = await client.get(
        f"/api/v1/analytics/category-breakdown?year={today.year}&month={today.month}",
        headers=auth_headers,
    )
    items = response.json()
    total_percent = sum(item["percent"] for item in items)
    assert 99.0 <= total_percent <= 100.01


async def test_daily_spend_reflects_created_expenses(client, auth_headers):
    today = date.today()
    category_id = await _category_id(client, auth_headers, "Health")
    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "75.00", "category_id": category_id, "date": str(today)},
    )
    response = await client.get(
        f"/api/v1/analytics/daily-spend?year={today.year}&month={today.month}", headers=auth_headers
    )
    matched = next(p for p in response.json() if p["day"] == today.day)
    assert float(matched["total"]) >= 75.0


async def test_top_merchants_orders_by_total_descending(client, auth_headers):
    today = date.today()
    category_id = await _category_id(client, auth_headers, "Shopping")

    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={
            "amount": "50.00",
            "category_id": category_id,
            "merchant": "SmallShop",
            "date": str(today),
        },
    )
    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={
            "amount": "500.00",
            "category_id": category_id,
            "merchant": "BigShop",
            "date": str(today),
        },
    )

    response = await client.get(
        f"/api/v1/analytics/top-merchants?year={today.year}&month={today.month}",
        headers=auth_headers,
    )
    merchants = [item["merchant"] for item in response.json()]
    assert merchants.index("BigShop") < merchants.index("SmallShop")
