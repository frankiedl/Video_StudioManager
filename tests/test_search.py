from vpm.database import Base, SessionLocal, engine
from vpm import models


def test_search_returns_projects_tasks_and_assets(monkeypatch, tmp_path):
    data_dir = tmp_path / "shared-data"
    monkeypatch.setenv("VPM_DATA_DIR", str(data_dir))

    import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        project = models.Project(
            name="Spot Verano",
            project_type="Vídeo",
            root_path=str(tmp_path / "project-root"),
            color="#3B82F6",
            statuses=["Backlog", "Done"],
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        task_list = models.TaskList(project_id=project.id, name="General")
        db.add(task_list)
        db.commit()
        db.refresh(task_list)

        task = models.Task(
            task_list_id=task_list.id,
            title="Revisar entrega",
            description="Buscar referencia",
            status="Backlog",
            priority="Alta",
        )
        db.add(task)
        db.commit()

        meta = models.AssetMeta(project_id=project.id, rel_path="assets/imagen.jpg", notes="Referencia de color")
        db.add(meta)
        db.commit()
    finally:
        db.close()

    from fastapi.testclient import TestClient

    with TestClient(app.app) as client:
        response = client.get("/api/search?q=referencia")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["type"] == "task" for item in payload)
    assert any(item["type"] == "asset" for item in payload)
    assert any(item["type"] == "project" for item in payload)
