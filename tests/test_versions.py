from fastapi.testclient import TestClient


def test_snapshots(monkeypatch, tmp_path):
    monkeypatch.setenv("VPM_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("VPM_AUTH", "on")
    import app
    from vpm.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    root = tmp_path / "proj"
    root.mkdir()
    f = root / "scene.blend"
    f.write_text("v1")

    c = TestClient(app.app)
    c.post("/api/auth/setup", json={"name": "A", "email": "a@x.com", "password": "supersecret1"})
    pid = c.post("/api/projects", json={"name": "P", "root_path": str(root), "create_structure": False}).json()["id"]
    body = {"project_id": pid, "rel_path": "scene.blend"}

    v1 = c.post("/api/versions", json={**body, "note": "primera"}).json()
    assert c.post("/api/versions", json=body).status_code == 400  # unchanged
    f.write_text("v2 changed")
    v2 = c.post("/api/versions", json=body).json()
    assert v2["sha256"] != v1["sha256"]
    assert len(c.get(f"/api/versions?project_id={pid}&rel_path=scene.blend").json()) == 2

    f.write_text("v3 unsaved work")
    assert c.post(f"/api/versions/{v1['id']}/restore").status_code == 200
    assert f.read_text() == "v1"
    versions = c.get(f"/api/versions?project_id={pid}&rel_path=scene.blend").json()
    assert len(versions) == 3 and versions[0]["note"].startswith("Auto")  # unsaved v3 kept
    assert c.get(f"/api/versions/{v2['id']}/download").content == b"v2 changed"

    # history follows a rename; hidden store isn't listed in the browser
    assert c.post("/api/files/rename", json={**body, "new_name": "final.blend"}).status_code == 200
    assert len(c.get(f"/api/versions?project_id={pid}&rel_path=final.blend").json()) == 3
    names = [e["name"] for e in c.get(f"/api/files/browse?project_id={pid}").json()["entries"]]
    assert names == ["final.blend"]
    assert c.delete(f"/api/versions/{v2['id']}").status_code == 200
