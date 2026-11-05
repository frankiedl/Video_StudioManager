from fastapi.testclient import TestClient


def test_project_permissions(monkeypatch, tmp_path):
    monkeypatch.setenv("VPM_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("VPM_AUTH", "on")
    import app
    from vpm.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.txt").write_text("x")

    admin = TestClient(app.app)
    admin.post("/api/auth/setup", json={"name": "A", "email": "a@x.com", "password": "supersecret1"})
    mk = lambda n: admin.post("/api/users", json={"name": n, "email": f"{n}@x.com", "password": "memberpass1"}).json()["id"]
    ids = {n: mk(n) for n in ("ed", "vw", "out")}
    clients = {}
    for n in ids:
        c = TestClient(app.app)
        assert c.post("/api/auth/login", json={"email": f"{n}@x.com", "password": "memberpass1"}).status_code == 200
        clients[n] = c

    pid = admin.post("/api/projects", json={"name": "P", "root_path": str(root), "create_structure": False}).json()["id"]
    for n, role in (("ed", "editor"), ("vw", "viewer")):
        assert admin.put(f"/api/projects/{pid}/members", json={"user_id": ids[n], "role": role}).status_code == 200

    # outsider sees nothing and cannot reach the project
    assert clients["out"].get("/api/projects").json() == []
    assert clients["out"].get(f"/api/files/browse?project_id={pid}").status_code == 404
    # viewer reads but can't write
    assert len(clients["vw"].get("/api/projects").json()) == 1
    assert clients["vw"].get(f"/api/files/browse?project_id={pid}").status_code == 200
    ren = {"project_id": pid, "rel_path": "a.txt", "new_name": "b.txt"}
    assert clients["vw"].post("/api/files/rename", json=ren).status_code == 403
    assert clients["vw"].post("/api/locks", json={"project_id": pid, "rel_path": "a.txt"}).status_code == 403
    # editor writes but can't manage members or delete
    assert clients["ed"].post("/api/locks", json={"project_id": pid, "rel_path": "a.txt"}).status_code == 200
    assert clients["ed"].put(f"/api/projects/{pid}/members", json={"user_id": ids["out"], "role": "viewer"}).status_code == 403
    assert clients["ed"].delete(f"/api/projects/{pid}").status_code == 403
    # a member who creates a project becomes its owner
    own = clients["ed"].post("/api/projects", json={"name": "Mine", "root_path": str(root), "create_structure": False}).json()["id"]
    assert clients["ed"].put(f"/api/projects/{own}/members", json={"user_id": ids["out"], "role": "viewer"}).status_code == 200
    assert len(clients["out"].get("/api/projects").json()) == 1
    # last owner can't be removed
    assert clients["ed"].delete(f"/api/projects/{own}/members/{ids['ed']}").status_code == 400
    # admin sees everything
    assert len(admin.get("/api/projects").json()) == 2
