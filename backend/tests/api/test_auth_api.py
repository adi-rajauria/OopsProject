REGISTER = {"email": "riya@corp.test", "full_name": "Riya Sharma", "password": "Secret123",
            "department": "Finance"}


def register_and_login(client) -> str:
    assert client.post("/api/auth/register", json=REGISTER).status_code == 201
    response = client.post("/api/auth/login", json={"email": REGISTER["email"], "password": "Secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_reports_database_up(client):
    assert client.get("/api/health").json() == {"status": "ok", "database": "up"}


def test_register_login_and_me(client):
    token = register_and_login(client)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "EMPLOYEE" and me.json()["code"] == "E1"


def test_invalid_login_returns_401_with_error_code(client):
    register_and_login(client)
    response = client.post("/api/auth/login", json={"email": REGISTER["email"], "password": "Wrong1234"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_protected_endpoint_requires_a_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    bad = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "INVALID_TOKEN"


def test_token_expires_after_configured_lifetime(client, clock):
    token = register_and_login(client)
    clock.advance(minutes=61)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_invalid_input_and_duplicate_registration(client):
    bad = client.post("/api/auth/register", json={**REGISTER, "email": "nope"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_INPUT"
    weak = client.post("/api/auth/register", json={**REGISTER, "password": "onlyletters"})
    assert weak.status_code == 422 and "digit" in weak.json()["error"]["message"]
    register_and_login(client)
    duplicate = client.post("/api/auth/register", json=REGISTER)
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_cors_allows_only_the_frontend_origin(client):
    allowed = client.options("/api/auth/login", headers={"Origin": "http://localhost:5173",
                                                         "Access-Control-Request-Method": "POST"})
    denied = client.options("/api/auth/login", headers={"Origin": "http://evil.example",
                                                        "Access-Control-Request-Method": "POST"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
