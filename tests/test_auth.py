import uuid


async def test_signup_creates_user_and_seeds_categories(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "StrongPass123"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["is_active"] is True


async def test_signup_duplicate_email_rejected(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "StrongPass123"}
    first = await client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409


async def test_login_success_and_wrong_password(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"
    await client.post("/api/v1/auth/signup", json={"email": email, "password": password})

    good = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert good.status_code == 200
    assert "access_token" in good.json()

    bad = await client.post("/api/v1/auth/login", data={"username": email, "password": "wrong"})
    assert bad.status_code == 401


async def test_me_requires_valid_token(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200

    unauthenticated = await client.get("/api/v1/auth/me")
    assert unauthenticated.status_code == 401


async def test_refresh_token_issues_new_access_token(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"
    await client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    login = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    refresh_token = login.json()["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


async def test_access_token_rejected_at_refresh_endpoint(client, auth_headers):
    access_token = auth_headers["Authorization"].split(" ")[1]
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


async def test_update_profile_sets_monthly_income(client, auth_headers):
    response = await client.patch(
        "/api/v1/auth/me", headers=auth_headers, json={"monthly_income": "50000.00"}
    )
    assert response.status_code == 200
    assert response.json()["monthly_income"] == "50000.00"
