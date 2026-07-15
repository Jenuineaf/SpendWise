import uuid
from datetime import date


async def _category_id(client, headers, name="Food & Dining"):
    response = await client.get("/api/v1/categories", headers=headers)
    for category in response.json():
        if category["name"] == name:
            return category["id"]
    raise AssertionError(f"default category {name} missing")


async def test_default_categories_seeded_on_signup(client, auth_headers):
    response = await client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert "Food & Dining" in names
    assert "Other" in names
    assert len(names) == 10


async def test_create_and_get_expense(client, auth_headers):
    category_id = await _category_id(client, auth_headers)
    create = await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={
            "amount": "250.50",
            "category_id": category_id,
            "merchant": "Swiggy",
            "date": str(date.today()),
        },
    )
    assert create.status_code == 201
    expense_id = create.json()["id"]

    fetched = await client.get(f"/api/v1/expenses/{expense_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["amount"] == "250.50"


async def test_expense_pagination(client, auth_headers):
    category_id = await _category_id(client, auth_headers)
    for _ in range(3):
        await client.post(
            "/api/v1/expenses",
            headers=auth_headers,
            json={"amount": "10.00", "category_id": category_id, "date": str(date.today())},
        )

    response = await client.get("/api/v1/expenses?page=1&page_size=2", headers=auth_headers)
    body = response.json()
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 3


async def test_expense_date_range_filter_excludes_out_of_range(client, auth_headers):
    category_id = await _category_id(client, auth_headers)
    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "42.00", "category_id": category_id, "date": "2020-01-15"},
    )

    response = await client.get(
        "/api/v1/expenses?date_from=2025-01-01&date_to=2025-12-31", headers=auth_headers
    )
    amounts = [item["amount"] for item in response.json()["items"]]
    assert "42.00" not in amounts


async def test_expenses_are_scoped_to_owner(client, auth_headers):
    category_id = await _category_id(client, auth_headers)
    create = await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "99.00", "category_id": category_id, "date": str(date.today())},
    )
    expense_id = create.json()["id"]

    other_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/signup", json={"email": other_email, "password": "StrongPass123"}
    )
    login = await client.post(
        "/api/v1/auth/login", data={"username": other_email, "password": "StrongPass123"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get(f"/api/v1/expenses/{expense_id}", headers=other_headers)
    assert response.status_code == 404


async def test_category_cannot_be_deleted_while_in_use(client, auth_headers):
    category_id = await _category_id(client, auth_headers)
    await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={"amount": "10.00", "category_id": category_id, "date": str(date.today())},
    )
    response = await client.delete(f"/api/v1/categories/{category_id}", headers=auth_headers)
    assert response.status_code == 409


async def test_recategorizing_expense_learns_override(client, auth_headers):
    food_id = await _category_id(client, auth_headers, "Food & Dining")
    shopping_id = await _category_id(client, auth_headers, "Shopping")

    create = await client.post(
        "/api/v1/expenses",
        headers=auth_headers,
        json={
            "amount": "500.00",
            "category_id": food_id,
            "merchant": "MyLocalStore",
            "date": str(date.today()),
        },
    )
    expense_id = create.json()["id"]

    patched = await client.patch(
        f"/api/v1/expenses/{expense_id}", headers=auth_headers, json={"category_id": shopping_id}
    )
    assert patched.status_code == 200
    assert patched.json()["category_id"] == shopping_id
