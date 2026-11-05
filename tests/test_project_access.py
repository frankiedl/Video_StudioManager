from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path, mode):
    monkeypatch.setenv("VPM_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("VPM_AUTH", "on")
    monkeypatch.delenv("VPM_MODE", raising=False)
    import app
    from vpm.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.txt").write_text("x")
    first = TestClient(app.app)
    first.post("/api/auth/setup", json={"name": "U1", "email": "u1@x.com", "password": "supersecret1", "mode": mode})
    users = {}
    clients = {"u1": first}
    for n in ("u2", "u3"):
        users[n] = first.post("/api/users", json={"name": n, "email": f"{n}@x.com", "password": "memberpass1"}).json()["id"]
        c = TestClient(app.app)
        assert c.post("/api/auth/login", json={"email": f"{n}@x.com", "password": "memberpass1"}).status_code == 200
        clients[n] = c
    return clients, users, root


def _mk(c, root, **extra):
    return c.post("/api/projects", json={"name": "P", "root_path": str(root), "create_structure": False, **extra}).json()


def test_personal_then_team_is_reversible(monkeypatch, tmp_path):
    cl, users, root = _setup(monkeypatch, tmp_path, "team")
    p = _mk(cl["u1"], root, access="personal")
    assert p["effective_access"] == "personal"
    pid = p["id"]
    assert cl["u2"].get("/api/projects").json() == []                      # hidden from others
    assert cl["u2"].get(f"/api/files/browse?project_id={pid}").status_code == 404
    assert cl["u1"].put(f"/api/projects/{pid}/members", json={"user_id": users["u2"]}).status_code == 400  # not shareable yet

    assert cl["u1"].patch(f"/api/projects/{pid}", json={"access": "team"}).json()["access"] == "team"
    assert cl["u1"].put(f"/api/projects/{pid}/members", json={"user_id": users["u2"], "role": "owner"}).json()["role"] == "editor"
    assert cl["u2"].get(f"/api/files/browse?project_id={pid}").status_code == 200
    rename = {"project_id": pid, "rel_path": "a.txt", "new_name": "b.txt"}
    assert cl["u2"].post("/api/files/rename", json=rename).status_code == 200   # equals: can write
    assert cl["u2"].put(f"/api/projects/{pid}/members", json={"user_id": users["u3"]}).status_code == 200  # and can invite
    assert cl["u3"].get(f"/api/projects/{pid}").status_code == 200

    # back to personal: others lose access, but nothing is deleted
    cl["u1"].patch(f"/api/projects/{pid}", json={"access": "personal"})
    assert cl["u2"].get(f"/api/projects/{pid}").status_code == 404
    cl["u1"].patch(f"/api/projects/{pid}", json={"access": "team"})
    assert cl["u2"].get(f"/api/projects/{pid}").status_code == 200           # reversible
    assert {m["user_id"] for m in cl["u1"].get(f"/api/projects/{pid}/members").json()} >= {users["u2"], users["u3"]}


def test_default_follows_app_mode_and_projects_can_differ(monkeypatch, tmp_path):
    cl, users, root = _setup(monkeypatch, tmp_path, "team")
    open_p = _mk(cl["u1"], root)                       # app in team mode: everyone sees it
    assert open_p["effective_access"] == "open" and open_p["access"] is None
    assert [p["id"] for p in cl["u2"].get("/api/projects").json()] == [open_p["id"]]
    studio_p = _mk(cl["u1"], root, access="studio")    # a studio-style project in the same app
    cl["u1"].put(f"/api/projects/{studio_p['id']}/members", json={"user_id": users["u2"], "role": "viewer"})
    assert cl["u2"].put(f"/api/projects/{studio_p['id']}/members", json={"user_id": users["u3"]}).status_code == 403  # viewer can't invite
    ids = {p["id"] for p in cl["u2"].get("/api/projects").json()}
    assert ids == {open_p["id"], studio_p["id"]}
    assert {p["id"] for p in cl["u3"].get("/api/projects").json()} == {open_p["id"]}   # not a member of the studio one
