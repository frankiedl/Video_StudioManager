from fastapi.testclient import TestClient


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("VPM_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("VPM_AUTH", "on")
    monkeypatch.delenv("VPM_MODE", raising=False)
    import app
    from vpm.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return app


def test_local_mode_needs_no_login(monkeypatch, tmp_path):
    app = _fresh(monkeypatch, tmp_path)
    c = TestClient(app.app)
    st = c.get("/api/auth/status").json()
    assert st["mode"] is None and st["needs_setup"] is True  # first-run chooser
    assert c.get("/api/projects").status_code == 401
    assert c.post("/api/auth/mode", json={"mode": "local"}).status_code == 200
    assert c.get("/api/projects").status_code == 200  # no login
    st = c.get("/api/auth/status").json()
    assert st["mode"] == "local" and st["auth_enabled"] is False
    assert c.post("/api/auth/mode", json={"mode": "local"}).status_code == 403  # already chosen


def test_team_mode_has_no_admin(monkeypatch, tmp_path):
    app = _fresh(monkeypatch, tmp_path)
    root = tmp_path / "proj"
    root.mkdir()
    one = TestClient(app.app)
    r = one.post("/api/auth/setup", json={"name": "U1", "email": "u1@x.com", "password": "supersecret1", "mode": "team"})
    assert r.status_code == 200 and r.json()["role"] == "member"
    assert one.get("/api/auth/status").json()["mode"] == "team"
    pid = one.post("/api/projects", json={"name": "P", "root_path": str(root), "create_structure": False}).json()["id"]
    # any member can add people...
    assert one.post("/api/users", json={"name": "U2", "email": "u2@x.com", "password": "memberpass1"}).status_code == 200
    two = TestClient(app.app)
    assert two.post("/api/auth/login", json={"email": "u2@x.com", "password": "memberpass1"}).status_code == 200
    # ...and everyone shares every project (no per-project permissions)
    assert [p["id"] for p in two.get("/api/projects").json()] == [pid]
    assert two.post("/api/users", json={"name": "U3", "email": "u3@x.com", "password": "memberpass1"}).status_code == 200
