USER = {"email": "Elip@Example.com", "password": "StrongPass123", "full_name": "Test User"}


def register_and_login(client):
    assert client.post("/api/auth/register", json=USER).status_code == 201
    r = client.post("/api/auth/login", data={"username": USER["email"], "password": USER["password"]})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_duplicate(client):
    client.post("/api/auth/register", json=USER)
    assert client.post("/api/auth/register", json=USER).status_code == 409


def test_register_weak_password(client):
    bad = {**USER, "password": "short"}
    assert client.post("/api/auth/register", json=bad).status_code == 422


def test_login_wrong_password(client):
    client.post("/api/auth/register", json=USER)
    r = client.post("/api/auth/login", data={"username": USER["email"], "password": "WrongPass123"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/users/me").status_code == 401


def test_profile_roundtrip(client):
    headers = register_and_login(client)
    payload = {
        "skills": ["Python", "python", " SQL ", "FastAPI"],
        "target_roles": ["AI Engineer"],
        "preferred_locations": ["Gurgaon"],
        "experience_level": "fresher",
    }
    r = client.put("/api/users/me/profile", json=payload, headers=headers)
    assert r.status_code == 200
    assert r.json()["skills"] == ["Python", "SQL", "FastAPI"]  # deduped + trimmed
    assert client.get("/api/users/me/profile", headers=headers).json()["target_roles"] == ["AI Engineer"]