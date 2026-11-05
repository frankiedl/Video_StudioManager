from fastapi.testclient import TestClient


def _client(monkeypatch):
    monkeypatch.setenv("VPM_AUTH", "on")
    import app
    from vpm.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(app.app)


def test_auth_flow(monkeypatch, tmp_path):
    monkeypatch.setenv("VPM_DATA_DIR", str(tmp_path))
    client = _client(monkeypatch)
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/auth/status").json()["needs_setup"] is True
    weak = {"name": "A", "email": "a@x.com", "password": "short"}
    assert client.post("/api/auth/setup", json=weak).status_code == 400
    ok = {"name": "A", "email": "a@x.com", "password": "supersecret1"}
    r = client.post("/api/auth/setup", json=ok)
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert client.get("/api/projects").status_code == 200
    again = {"name": "B", "email": "b@x.com", "password": "supersecret1"}
    assert client.post("/api/auth/setup", json=again).status_code == 403
    member = {"name": "M", "email": "m@x.com", "password": "memberpass1"}
    assert client.post("/api/users", json=member).status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/projects").status_code == 401
    bad = {"email": "m@x.com", "password": "bad"}
    assert client.post("/api/auth/login", json=bad).status_code == 401
    good = {"email": "m@x.com", "password": "memberpass1"}
    assert client.post("/api/auth/login", json=good).status_code == 200
    newu = {"name": "N", "email": "n@x.com"}
    assert client.post("/api/users", json=newu).status_code == 403
