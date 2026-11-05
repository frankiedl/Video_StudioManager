from fastapi.testclient import TestClient


def test_lock_flow(monkeypatch, tmp_path):
    monkeypatch.setenv("VPM_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("VPM_AUTH", "on")
    import app
    from vpm.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.blend").write_text("x")

    admin = TestClient(app.app)
    admin.post("/api/auth/setup", json={"name": "A", "email": "a@x.com", "password": "supersecret1"})
    pid = admin.post("/api/projects", json={"name": "P", "root_path": str(root), "create_structure": False}).json()["id"]
    mid = admin.post("/api/users", json={"name": "M", "email": "m@x.com", "password": "memberpass1"}).json()["id"]
    admin.put(f"/api/projects/{pid}/members", json={"user_id": mid, "role": "editor"})
    member = TestClient(app.app)
    member.post("/api/auth/login", json={"email": "m@x.com", "password": "memberpass1"})

    body = {"project_id": pid, "rel_path": "a.blend"}
    assert admin.post("/api/locks", json=body).status_code == 200
    assert member.post("/api/locks", json=body).status_code == 409
    rename = {"project_id": pid, "rel_path": "a.blend", "new_name": "b.blend"}
    assert member.post("/api/files/rename", json=rename).status_code == 409
    listing = member.get(f"/api/files/browse?project_id={pid}").json()
    assert listing["entries"][0]["lock"] is not None
    assert member.delete(f"/api/locks?project_id={pid}&rel_path=a.blend").status_code == 403
    assert admin.post("/api/files/rename", json=rename).status_code == 200  # owner may rename
    moved = admin.get(f"/api/locks?project_id={pid}").json()
    assert moved[0]["rel_path"] == "b.blend"  # lock followed the rename
    assert admin.delete(f"/api/locks?project_id={pid}&rel_path=b.blend").status_code == 200
    assert member.post("/api/locks", json={"project_id": pid, "rel_path": "b.blend"}).status_code == 200
